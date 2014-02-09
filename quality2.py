#####################################################
#                                                   #
#   Predicting risk of bias from full text papers   #
#                                                   #
#####################################################
import pdb 

from tokenizer import sent_tokenizer, word_tokenizer
import biviewer
import re
import progressbar
import collections
import string
from unidecode import unidecode
import codecs

import yaml
from pprint import pprint

import numpy as np
import math

import sklearn
from sklearn.feature_extraction.text import CountVectorizer
from sklearn import cross_validation
from sklearn import metrics
from sklearn import svm
from sklearn.linear_model import SGDClassifier

import random

from sklearn.cross_validation import KFold



from collections import Counter

QUALITY_QUOTE_REGEX = re.compile("Quote\:\s*[\'\"](.*?)[\'\"]")

CORE_DOMAINS = ["Random sequence generation", "Allocation concealment", "Blinding of participants and personnel",
                "Blinding of outcome assessment", "Incomplete outcome data", "Selective reporting"]
                # there is a seventh domain "Other", but not listed here since covers multiple areas
                # see data/domain_names.txt for various other criteria
                # all of these are available via QualityQuoteReader



def word_sent_tokenize(raw_text):
    return [(word_tokenizer.tokenize(sent)) for sent in sent_tokenizer.tokenize(raw_text)]


def describe_data():

    perdomain_output = [Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter()]
    perdomain_quotes = [Counter(), Counter(), Counter(), Counter(), Counter(), Counter(), Counter()]

    overall_output = Counter()
    overall_quotes = Counter()

    q = QualityQuoteReader()

    for i, study in enumerate(q):
            
        for domain in study.cochrane["QUALITY"]:

            domain_text = domain["DOMAIN"].replace("\xc2\xa0", " ")

            if domain_text in CORE_DOMAINS:
                domain_index = CORE_DOMAINS.index(domain_text)
            else:
                domain_index = 6 # other

            perdomain_output[domain_index][domain["RATING"]] += 1
            overall_output[domain["RATING"]] += 1

            if QUALITY_QUOTE_REGEX.match(domain['DESCRIPTION']):
                perdomain_quotes[domain_index][domain["RATING"]] += 1
                overall_quotes[domain["RATING"]] += 1

    print
    print "ALL"
    for domain, counts in zip(CORE_DOMAINS + ["OTHER"], perdomain_output):
        print
        print domain
        print
        print counts

    print
    print "OVERALL"
    print
    print overall_output



def flatten_list(l):
    return [item for sublist in l for item in sublist]


def sublist(l, indices):
    if isinstance(indices, tuple):
        indices = [indices]

    output = [l[start: end] for (start, end) in indices]
    return flatten_list(output)

def np_indices(indices):
    if isinstance(indices, tuple):
        indices = [indices]

    output = [np.arange(start, end) for (start, end) in indices]
    return np.hstack(output)


def show_most_informative_features(vectorizer, clf, n=50):
    ###
    # note that in the multi-class case, clf.coef_ will
    # have k weight vectors, which I believe are one per
    # each class (i.e., each is a classifier discriminating
    # one class versus the rest). 
    c_f = sorted(zip(clf.coef_[2], vectorizer.get_feature_names()))

    if n == 0:
        n = len(c_f)/2

    top = zip(c_f[:n], c_f[:-(n+1):-1])
    print
    print "%d most informative features:" % (n, )
    out_str = []
    for (c1, f1), (c2, f2) in top:
        out_str.append("\t%.4f\t%-15s\t\t%.4f\t%-15s" % (c1, f1, c2, f2))
    feature_str = "\n".join(out_str)
    return (feature_str, top)

def load_domain_map(filename="data/domain_names.txt"):

    with codecs.open(filename, 'rb', 'utf-8') as f:
        raw_data = yaml.load(f)

    mapping = {}

    for key, value in raw_data.iteritems():
        for synonym in value:
            mapping[synonym] = key

    return mapping

class QualityQuoteReader():
    """
    iterates through Cochrane Risk of Bias information for domains where there is a quote only
    """

    def __init__(self, quotes_only=True):
        self.BiviewerView = collections.namedtuple('BiViewer_View', ['cochrane', 'studypdf'])
        self.pdfviewer = biviewer.PDFBiViewer()
        self.domain_map = load_domain_map()
        self.quotes_only = quotes_only


    def __iter__(self):
        """
        run through PDF/Cochrane data, and return filtered data of interest
        preprocesses PDF text
        and maps domain title to one of the core Risk of Bias domains if possible
        """

        used_pmids = set()

        p = progressbar.ProgressBar(len(self.pdfviewer), timer=True)

        for study in self.pdfviewer:

            p.tap()

            quality_quotes = []
            quality_data = study.cochrane["QUALITY"]


            for domain in quality_data:
                domain['DESCRIPTION'] = self.preprocess_cochrane(domain['DESCRIPTION'])
                if QUALITY_QUOTE_REGEX.match(domain['DESCRIPTION']) or not self.quotes_only:
                    domain_text = domain["DOMAIN"].replace("\xc2\xa0", " ")

                    try:
                        domain["DOMAIN"] = self.domain_map[domain_text] # map domain titles to our core categories
                    except:
                        domain["DOMAIN"] = "UNMAPPED"
                    quality_quotes.append(domain)

            if quality_quotes:
                yield self.BiviewerView(cochrane={"QUALITY": quality_quotes}, studypdf=self.preprocess_pdf(study.studypdf))
                # returns only the quality data with quotes in it for ease of use; preprocesses pdf text


    def preprocess_pdf(self, pdftext):
        pdftext = unidecode(pdftext)
        pdftext = re.sub("\n", " ", pdftext) # preprocessing rule 1
        return pdftext

    def preprocess_cochrane(self, cochranetext):
        cochranetext = unidecode(cochranetext)
        return cochranetext

    def domains(self):
        domain_headers = set((value for key, value in self.domain_map.iteritems()))
        return list(domain_headers)






def _get_domains_from_study(study):
    return [domain["DOMAIN"] for domain in study.cochrane["QUALITY"]]

def _simple_BoW(study):
    return [s for s in word_tokenizer.tokenize(study.studypdf) 
                if not s in string.punctuation]

def to_TeX(all_res):
    tex_table = ['''\\begin{table*}\n \\begin{tabular}{l | l l l l} \n Quality domain & \emph{high risk} F (\#) & \emph{unknown} F (\#) & \emph{low risk} F (\#) & top terms \\\\ \n \hline''']
    for domain in all_res:
        cur_row = domain + " & "
        res_matrix = all_res[domain][0]
        cur_row += _to_TeX(res_matrix) 

        # add terms
        terms = all_res[domain][1][1]
        print "\n\n"
        print domain
        print [t[1] for t in terms[:20]]
        
        top_three = [t[1][1] for t in terms[:3]]
        cur_row += " & %s" % "; ".join(["\\emph{%s}" % t for t in top_three])
        cur_row +=  "\\\\"
        tex_table.append(cur_row)


    tex_table.append("\end{tabular} \n \end{table*}")
    return "\n".join(tex_table)

def _to_TeX(res):
    '''
    Assume res is like:

    [  1.18793103e-01   6.78426907e-01   7.03841752e-01]
     [  4.09195402e-02   7.47927854e-01   6.73109244e-01]
     [  5.63686201e-02   7.10841025e-01   6.86779839e-01]
     [  2.92000000e+01   2.69800000e+02   2.38000000e+02]

     this is [row index]: [0] precision, [1] recall, [2] F [3] support
     for each of [column index]: [0] no, [1] unknown [2] yes
    '''
    f_scores = res[2]
    support = res[3]
    tex_row_str = "%.3f (%.1f) & %.3f (%.1f) & %.3f (%.1f)" % (
        f_scores[0], support[0], f_scores[1], support[1], 
        f_scores[2], support[2])
    return tex_row_str


def _get_study_level_X_y(test_domain=CORE_DOMAINS[0]):
    '''
    return X, y for the specified test domain. here
    X will be of dimensionality equal to the number of 
    studies for which we have the test_domain data. 
    '''
    X, y = [], []
    #study_counter = 0
    q = QualityQuoteReader(quotes_only=False)


    # creates binary task
    #map_lbl = lambda lbl: 1 if lbl=="YES" else -1
    map_lbl = lambda lbl: {"YES":2, "NO":0, "UNKNOWN":1}[lbl]
    for i, study in enumerate(q):
        domain_in_study = False
        pdf_tokens = study.studypdf
            

        for domain in study.cochrane["QUALITY"]:

            quality_rating = domain["RATING"]
            #### for now skip unknowns, test YES v NO
            #if quality_rating == "UNKNOWN":
            #    quality_rating = "NO"
                # break

            # note that the 2nd clause deals with odd cases 
            # in which a domain is *repeated* for a study,
            if domain["DOMAIN"] == test_domain and not domain_in_study:

                domain_in_study = True
                #study_counter += 1
                #pdf_tokens = word_sent_tokenize(study.studypdf)

                X.append(pdf_tokens)
                #y.append(map_lbl(quality_rating))
                y.append(quality_rating)
        
                
        if not domain_in_study:
            #y.append("MISSING")
            pass
            
        
        if i > 500:
            print "WARNING RETURNING SMALL SUBSET OF DATA!"
            break
        #if len(y) != len(X):
        #    pdb.set_trace()
        
    #pdb.set_trace()
    vectorizer = CountVectorizer(max_features=5000, binary=True)
    Xvec = vectorizer.fit_transform(X)            
    #pdb.set_trace()
    return Xvec, y, vectorizer


def predict_domains_for_documents(test_domain=CORE_DOMAINS[0], avg=True):
    X, y, vectorizer = _get_study_level_X_y(test_domain=test_domain)
    score_f = lambda y_true, y_pred : metrics.precision_recall_fscore_support(
                                            y_true, y_pred, average=None)#, average="macro")
    #score_f = sklearn.metrics.f1_score

    # note that asarray call below, which seems necessary for 
    # reasons that escape me (see here 
    # https://github.com/scikit-learn/scikit-learn/issues/2508)

    clf = SGDClassifier(loss="hinge", penalty="l2", alpha=.01)
    #pdb.set_trace()
    cv_res = cross_validation.cross_val_score(
                clf, X, np.asarray(y), 
                score_func=score_f, 
                #sklearn.metrics.precision_recall_fscore_support,
                cv=5)
    #pdb.set_trace()
    if avg:
        cv_res = sum(cv_res)/float(cv_res.shape[0])
    #metrics.precision_recall_fscore_support
    
    #if dump_output:
    #    np.savetxt(test_domain.replace(" ", "_") + ".csv", cv_res, delimiter=',', fmt='%2.2f')

    print cv_res

    ### train on all
    model = clf.fit(X, y)
    informative_features = show_most_informative_features(vectorizer, model, n=50)
    return (cv_res, informative_features, y)

def predict_all_domains():
    # need to label mapping
    results_d = {}
    for domain in CORE_DOMAINS:
        print ("on domain: {0}".format(domain))
        results_d[domain] = predict_domains_for_documents(test_domain=domain)
    return results_d


    
def joint_predict_sentences_reporting_bias():
    '''
    @TODO bcw

    1. For each fold, augment training data with true labels
    2. Train as usual (with augmented feature vectors)
    3. Make predictions at the *document level* for specified domain
    4. Augment test vectors with predicted labels
    5. bam
    '''
    
    # first, get the true document-level labels
    study_X, study_y, study_vectorizer = _get_study_level_X_y()

    # here are the sentence level X,y's
    X, y, X_sents, vec, study_sent_indices = _get_sentence_level_X_y()

    # now cross-validate
    clf = SGDClassifier(loss="hinge", penalty="l2")
    kf = KFold(len(study_sent_indices), n_folds=5, shuffle=True)

    for fold_i, (train, test) in enumerate(kf):
        test_indices = [study_sent_indices[i] for i in test]
        train_indices = [study_sent_indices[i] for i in train]

        # again, these are sentence level features
        X_sents_test = sublist(X_sents, test_indices)

        # train/test split
        X_train = X[np_indices(train_indices)]
        y_train = y[np_indices(train_indices)]
        X_test = X[np_indices(test_indices)]
        y_test = y[np_indices(test_indices)]
        
        ###
        # now we want to augment vectors with study-level
        # information. specifically, create a copy of
        # the feature set that is an interaction with
        # the study-level bias assessment
        ###

        pdb.set_trace()


def predict_sentences_reporting_bias(negative_sample_weighting=1, number_of_models=1, positives_per_pdf=1):
    X, y, X_sents, vec, study_sent_indices = _get_sentence_level_X_y()
    

    


    kf = KFold(len(study_sent_indices), n_folds=5, shuffle=True)

    metrics = []

    for fold_i, (train, test) in enumerate(kf):

        print "making test sentences"
        
        test_indices = [study_sent_indices[i] for i in test]
        train_indices = [study_sent_indices[i] for i in train]

        X_sents_test = sublist(X_sents, test_indices)
        # [X_sents[i] for i in test]
        
        print "done!"

        # print "generating split"
        X_train = X[np_indices(train_indices)]
        y_train = y[np_indices(train_indices)]
        X_test = X[np_indices(test_indices)]
        y_test = y[np_indices(test_indices)]
        # print "done!"

        

        all_indices = np.arange(len(y_train))


        train_positives = np.nonzero(y_train)[0]
        train_negatives = all_indices[~train_positives]

        total_positives = len(train_positives)



        if (negative_sample_weighting * total_positives) > len(train_negatives):
            sample_negative_examples = len(train_negatives)
        else:
            sample_negative_examples = negative_sample_weighting * total_positives


        models = []

        print "fitting models..."
        p = progressbar.ProgressBar(number_of_models, timer=True)

        for model_no in range(number_of_models):

            p.tap()


            train_negatives_sample = np.random.choice(train_negatives, sample_negative_examples, replace=False)


            train_sample = np.concatenate([train_positives, train_negatives_sample])

            
            clf = SGDClassifier(loss="hinge", penalty="l2")
            clf.fit(X_train[train_sample], y_train[train_sample])
            models.append(clf)


        


        TP = 0
        FP = 0
        TN = 0
        FN = 0

        print "testing..."
        p = progressbar.ProgressBar(len(test_indices), timer=True)

        for start, end in test_indices:

            p.tap()
            study_X = X[np_indices((start, end))]
            study_y = y[np_indices((start, end))]

            
            
            preds_all = np.mean([clf.predict(study_X) for clf in models], 0)

            max_indices = preds_all.argsort()[-positives_per_pdf:][::-1] + start
        
        
            real_index = np.where(study_y==1)[0][0] + start

            if real_index in max_indices:

                TP += 1
                TN += (len(study_y) - positives_per_pdf)
                FP += (positives_per_pdf - 1)
                # FN += 0
            else:
                # TP += 0
                TN += (len(study_y) - positives_per_pdf - 1) 
                FN += 1
                FP += positives_per_pdf

            print len(study_y)
            

        precision = float(TP) / (float(TP) + float(FP))
        recall = float(TP) / (float(TP) + float(FN))
        f1 = 2 * ((precision * recall) / (precision + recall))
        accuracy = float(TP) / len(test_indices)

        metrics.append({"precision": precision,
                        "recall": recall,
                        "f1": f1,
                        "accuracy": accuracy})



    print
    pprint(metrics)

    metric_types = ["precision", "recall", "f1", "accuracy"]

    for metric_type in metric_types:

        metric_vec = [metric[metric_type] for metric in metrics]

        metric_mean = np.mean(metric_vec)

        print "%s: %.5f" % (metric_type, metric_mean)


    # print show_most_informative_features(vec, model, n=50)


    


def _get_sentence_level_X_y(test_domain=CORE_DOMAINS[0]):
    # sample_negative_examples = n: for low rate of positive examples; random sample
    # of n negative examples if > n negative examples in article; if n=0 then all examples
    # used


    q = QualityQuoteReader()
    y = []
    X_words = []
    
    study_sent_indices = [] # list of (start, end) indices corresponding to each study
    sent_index_counter = 0


    domains = q.domains()
    counter = 0

    for i, study in enumerate(q):

        # fast forward to the matching domain
        for domain in study.cochrane["QUALITY"]:
            if domain["DOMAIN"] == test_domain:
                break
        else:
            # if no matching domain continue to the next study
            continue


        try:
            quote = QUALITY_QUOTE_REGEX.search(domain["DESCRIPTION"]).group(1)
        except:
            print "Unable to extract quote:"
            print domain["DESCRIPTION"]
            raise

        quote_words = word_tokenizer.tokenize(quote)
        pdf_sents = sent_tokenizer.tokenize(study.studypdf)

 
        quote_sent_bow = set((word.lower() for word in quote_words))

        rankings = []

        for pdf_i, pdf_sent in enumerate(pdf_sents):

            pdf_words = word_tokenizer.tokenize(pdf_sent)
        
            pdf_sent_bow = set((word.lower() for word in pdf_words))

            if not pdf_sent_bow or not quote_sent_bow:
                prop_quote_in_sent = 0
            else:
                prop_quote_in_sent = 100* (1 - (float(len(quote_sent_bow-pdf_sent_bow))/float(len(quote_sent_bow))))

            # print "%.0f" % (prop_quote_in_sent,)

            rankings.append((prop_quote_in_sent, pdf_i))

        rankings.sort(key=lambda x: x[0], reverse=True)
        best_match_index = rankings[0][1]
        # print quote
        # print pdf_tokens[best_match_index]




        y_study = np.zeros(len(pdf_sents))
        y_study[best_match_index] = 1
        X_words.extend(pdf_sents)



        sent_end_index = sent_index_counter + len(pdf_sents)
        study_sent_indices.append((sent_index_counter, sent_end_index))
        sent_index_counter = sent_end_index
        y.extend(y_study)

        if i > 500:
            print "WARNING RETURNING SMALL SUBSET OF DATA!"
            break


                    
                    
                


    print len(X_words)
    print X_words[0]

    print "fitting vectorizer"
    vectorizer = CountVectorizer(max_features=10000)
    X = vectorizer.fit_transform(X_words)            
    print "done!"
    y = np.array(y)

    return X, y, X_words, vectorizer, study_sent_indices

    print "Finished! %d studies included domain %s" % (counter, test_domain)




def test_pdf_cache():

    pdfviewer = biviewer.PDFBiViewer()
    pdfviewer.cache_pdfs()


if __name__ == '__main__':
    # predict_domains_for_documents()
    # test_pdf_cache()
    predict_sentences_reporting_bias(negative_sample_weighting=1, number_of_models=100, positives_per_pdf=5)
    # getmapgaps()