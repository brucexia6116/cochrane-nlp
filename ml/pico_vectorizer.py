import numpy as np

import sklearn 
from scipy.sparse import lil_matrix, csc_matrix
import numpy as np
import scipy as sp
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer

from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import normalize
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords

from cochranenlp.textprocessing.drugbank import Drugbank

# PICO_vectorizer
#   a vectorizer class for extracting
#   features from sentences for learning
#   the distant supervised model

class PICO_vectorizer:

    def __init__(self):
        self.vectorizer = CountVectorizer(min_df=3, max_features=50000, ngram_range=(1, 2))
        self.dict_vectorizer = DictVectorizer() # used to pass non-textual features
        self.drugbank = Drugbank()

    def is_number(self,num):
        try:
            float(num)
            return True
        except ValueError:
            return False

    def fit(self, sentences, extra_features=None):
        print "fitting sentence dict"
        self.vectorizer.fit(sentences)

        print "fitting additional features (a list of dicts is available)"
        if extra_features is not None:
            self.dict_vectorizer.fit(extra_features)

    def transform(self, sentences, extra_features=None):

        print "ok, extracting text features"
        X = self.vectorizer.transform(sentences)
        tf_transformer = TfidfTransformer().fit(X)
        X_text = tf_transformer.transform(X)

        print "ok, extracting (binary!) numeric features!"
        #extract numeric features from sentences
        X_numeric = self.extract_numeric_features(sentences)

        if extra_features:
            print "ok, extracting additional features (a list of dicts is available)"
            X_extra_features = self.dict_vectorizer.transform(extra_features)
            print "combining features"
            #now combine feature sets.
            feature_matrix = sp.sparse.hstack((X_text, X_numeric, X_extra_features)).tocsr()

        else:
            print "combining features"
            #now combine feature sets.
            feature_matrix = sp.sparse.hstack((X_text, X_numeric)).tocsr()
        #returning the vectorizer and feature matrix
        #need to figure out if we need to return vectorizer
        return feature_matrix
    
    def fit_transform(self, sentences, extra_features=None):
        self.fit(sentences, extra_features)
        f_matrix = self.transform(sentences, extra_features)
        return f_matrix
    
    def extract_numeric_features(self,sentences, normalize_matrix=False):
        # number of numeric features (this is fixed
        # for now; may wish to revisit this)
        m = 6
        n = len(sentences)
        X_numeric = lil_matrix((n,m))#sp.sparse.csc_matrix((n,m))
        for sentence_index, sentence in enumerate(sentences):
            X_numeric[sentence_index, :] = self.extract_structural_features(sentence)
        # column-normalize
        X_numeric = X_numeric.tocsc()
        if normalize_matrix:
            X_numeric = normalize(X_numeric, axis=0)
        return X_numeric

    def extract_structural_features(self,sentence):
        fv = np.zeros(6)
        fv[0] = 1 if sentence.count("\n") > 20 else 0
        fv[1] = 1 if sentence.count("\n") > 50 else 0
        tokens = word_tokenize(sentence)
        num_numbers = sum([self.is_number(t) for t in tokens])
        if num_numbers > 0:
            num_frac = num_numbers / float(len(tokens))
            fv[2] = 1.0 if num_frac > .2 else 0.0
            fv[3] = 1.0 if num_frac > .4 else 0.0
        if len(tokens):
            average_token_len = np.mean([len(t) for t in tokens])
            fv[4] = 1 if average_token_len < 4 else 0
        fv[5] = self.drugbank.contains_drug(sentence)
        return fv

        