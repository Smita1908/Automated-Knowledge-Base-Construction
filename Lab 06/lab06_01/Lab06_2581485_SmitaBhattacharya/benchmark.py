''' 
Usage:
   benchmark --gold=GOLD_OIE --out=OUTPUT_FILE ( --clausie=CLAUSIE_OIE)

Options:
  --gold=GOLD_OIE              The gold reference Open IE file (by default, it should be under ./oie_corpus/all.oie).
  --out-OUTPUT_FILE            The output file, into which the precision recall curve will be written.
  --clausie=CLAUSIE_OIE        Read ClausIE format from file CLAUSIE_OIE.
 
'''
import docopt
import string
import numpy as np
from sklearn.metrics import precision_recall_curve
import re
import docopt
import logging
import nltk


logging.basicConfig(level = logging.INFO)

from oie_readers.clausieReader import ClausieReader

from oie_readers.goldReader import GoldReader
from oie_readers.matcher import Matcher

class Benchmark:
    ''' Compare the gold OIE dataset against a predicted equivalent '''
    def __init__(self, gold_fn):
        ''' Load gold Open IE, this will serve to compare against using the compare function '''
        gr = GoldReader() 
        gr.read(gold_fn)
        self.gold = gr.oie

    def compare(self, predicted, matchingFunc, output_fn):
        ''' Compare gold against predicted using a specified matching function. 
            Outputs PR curve to output_fn '''
        
        y_true = []
        y_scores = []
        
        correctTotal = 0
        unmatchedCount = 0        
        predicted = Benchmark.normalizeDict(predicted)
        gold = Benchmark.normalizeDict(self.gold)
                
        for sent, goldExtractions in list(gold.items()):
            if sent not in predicted:
                # The extractor didn't find any extractions for this sentence
                unmatchedCount += len(goldExtractions)
                correctTotal += len(goldExtractions)
                continue
                
            predictedExtractions = predicted[sent]
            
            for goldEx in goldExtractions:
                correctTotal += 1
                found = False
                
                for predictedEx in predictedExtractions:
                    if matchingFunc(goldEx, 
                                    predictedEx, 
                                    ignoreStopwords = True, 
                                    ignoreCase = True):
                        
                        y_true.append(1)
                        y_scores.append(predictedEx.confidence)
                        predictedEx.matched.append(output_fn)

                        # Also mark any other predictions with the
                        # same exact predicate as matched.
                        # This is to support packages that do conjunction
                        # splitting, and doesn't affect the results for
                        # packages that don't.
                        if predictedEx.splits_conjunctions:
                            for otherPredictedEx in predictedExtractions:
                                if otherPredictedEx.pred == predictedEx.pred:
                                    otherPredictedEx.matched.append(output_fn)

                        found = True
                        break
                    
                if not found:
                    unmatchedCount += 1
                    
            for predictedEx in [x for x in predictedExtractions if (output_fn not in x.matched)]:
                # Add false positives
                y_true.append(0)
                y_scores.append(predictedEx.confidence)
                
        y_true = y_true
        y_scores = y_scores
        
        # recall on y_true, y  (r')_scores computes |covered by extractor| / |True in what's covered by extractor|
        # to get to true recall we do r' * (|True in what's covered by extractor| / |True in gold|) = |true in what's covered| / |true in gold|
        p, r = Benchmark.prCurve(np.array(y_true), np.array(y_scores),
                       recallMultiplier = ((correctTotal - unmatchedCount)/float(correctTotal)))

        # write PR to file
        with open(output_fn, 'w') as fout:
            fout.write('{0}\t{1}\n'.format("Precision", "Recall"))
            f1 = 0.0
            for cur_p, cur_r in sorted(zip(p, r), key = lambda cur_p_cur_r: cur_p_cur_r[1]):
                fout.write('{0}\t{1}\n'.format(cur_p, cur_r))
                tmpf1 = 2 * cur_p * cur_r / (cur_p + cur_r)
                if tmpf1 > f1:
                    f1 = tmpf1
            fout.write("Maximal F1 score: " + str(f1))
            print("\nMaximal F1 score: " + str(f1) + "\n")
    
    @staticmethod
    def prCurve(y_true, y_scores, recallMultiplier):
        # Recall multiplier - accounts for the percentage examples unreached by 
        precision, recall, _ = precision_recall_curve(y_true, y_scores)
        recall = recall * recallMultiplier
        return precision, recall

    # Helper functions:
    @staticmethod
    def normalizeDict(d):
        return dict([(Benchmark.normalizeKey(k), v) for k, v in list(d.items())])
    
    @staticmethod
    def normalizeKey(k):
        return Benchmark.removePunct(str(Benchmark.PTB_unescape(k.replace(' ',''))))

    @staticmethod
    def PTB_escape(s):
        for u, e in Benchmark.PTB_ESCAPES:
            s = s.replace(u, e)
        return s
    
    @staticmethod
    def PTB_unescape(s):
        for u, e in Benchmark.PTB_ESCAPES:
            s = s.replace(e, u)
        return s
    
    @staticmethod
    def removePunct(s):
        return Benchmark.regex.sub('', s)
    
    # CONSTANTS
    regex = re.compile('[%s]' % re.escape(string.punctuation))
    
    # Penn treebank bracket escapes 
    # Taken from: https://github.com/nlplab/brat/blob/master/server/src/gtbtokenize.py
    PTB_ESCAPES = [('(', '-LRB-'),
                   (')', '-RRB-'),
                   ('[', '-LSB-'),
                   (']', '-RSB-'),
                   ('{', '-LCB-'),
                   ('}', '-RCB-'),]


if __name__ == '__main__':
    args = docopt.docopt(__doc__)
    logging.debug(args)
    
    if args['--clausie']:
        predicted = ClausieReader()
        predicted.read(args['--clausie'])

    b = Benchmark(args['--gold'])
    out_filename = args['--out']

    logging.info("Writing PR curve of {} to {}".format(predicted.name, out_filename))
    b.compare(predicted = predicted.oie, 
               matchingFunc = Matcher.lexicalMatch,
               output_fn = out_filename)
    
        
        
