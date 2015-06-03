import csv
import pdb
import sys
reload(sys)
sys.setdefaultencoding('utf8')

import numpy as np 

from sklearn import metrics

import matplotlib.pyplot as plt

fields = ["CHAR_PARTICIPANTS", "CHAR_INTERVENTIONS", "CHAR_OUTCOMES"]


def generate_plots(nguyen_path, sds_path):
    lbls_n, lbls2_n, scores_n = _read_lbls_and_scores(nguyen_path)
    fpr_n, tpr_n, thresholds_n = metrics.roc_curve(lbls_n, scores_n)
    auc_n =  metrics.auc(fpr_n, tpr_n)

    lbls_sds, lbls2_sds, scores_sds = _read_lbls_and_scores(sds_path)
    fpr_sds, tpr_sds, thresholds_sds = metrics.roc_curve(lbls_sds, scores_sds)
    auc_sds =  metrics.auc(fpr_sds, tpr_sds)

    ### 
    # ok, plotting time
    plt.figure()
    plt.plot(fpr_n, tpr_n, label='Nguyen (area = %0.2f)' % auc_n)
    plt.plot(fpr_sds, tpr_sds, label='SDS (area = %0.2f)' % auc_sds)
    plt.legend(loc="lower right")
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('ROCs (for level 1 relevance)')
    plt.savefig("ROCs.pdf")


# e.g., fpath="1433334082-results-sds_all_sentence_scores.txt"
def AUCs(fpath):
    lbls, lbls2, scores = _read_lbls_and_scores(fpath)
    fpr, tpr, thresholds = metrics.roc_curve(lbls, scores)
    auc =  metrics.auc(fpr, tpr)
    print "auc 1: %s" % auc

    fpr, tpr, thresholds = metrics.roc_curve(lbls2, scores)
    auc =  metrics.auc(fpr, tpr)
    print "auc 2: %s" % auc


def _read_lbls_and_scores(fpath):
    lbls, lbls2, scores = [], [], []
    with open(fpath, 'rU') as all_scores_f:
        all_scores = csv.reader(all_scores_f)
        all_scores.next() # headers
        for pmid, sentence, raw_pred, lbl1, lbl2 in all_scores:
            lbls.append(int(lbl1))
            lbls2.append(int(lbl2))
            scores.append(float(raw_pred))    

    return np.array(lbls), np.array(lbls2), np.array(scores)

def average_results(results_file_path, target_variable="at least one (>=1):", 
                        field="CHAR_PARTICIPANTS"):
    results = []
    relevant_field = False
    with open(results_file_path, 'rU') as results_file:
        for l in results_file:
            if "domain: %s" % field in l:
                relevant_field = True
            
            if target_variable in l and (field is None or relevant_field): 
                cur_result = float(l.split(target_variable)[1])
                results.append(cur_result)
                relevant_field = False 
    #pdb.set_trace()
    return results

def make_report(results_file_path, target_variable="at least one (>=1):"):
    out_str = ["results for %s" % results_file_path]
    for field in fields:
        result_set = average_results(results_file_path, field=field, target_variable=target_variable)
        #pdb.set_trace()
        out_str.append("%s -- mean: %s, sd: %s" % (field, np.mean(result_set), np.std(result_set)))
    print "\n".join(out_str)
    #return out_str 

def dump(output, csv_path):
    with open(csv_path, 'wb') as output_f:
        csv_writer = csv.writer(output_f)
        csv_writer.writerows(output)

def gen_output_file(results_file_path, output_to_file=True):
    output_str = [["study id", "domain", "target text", "candidate text"]]
    results_stream = open(results_file_path, 'rb')

    cur_field = None
    cur_study_id = None 

    in_target_text = False 
    cur_target_text = ""

    in_candidate_text = False 
    cur_candidate_text = ""

    n = 0 
    for i,l in enumerate(results_stream.readlines()):
        if "-- domain" in l:
            if n > 0:
                output_str.append([cur_study_id, cur_field, cur_target_text, cur_candidate_text])
            n += 1
            in_candidate_text = False
            in_target_text = False
            cur_candidate_text = ""
            cur_target_text = ""

            if "CHAR_PARTICIPANTS" in l:
                cur_field = "population"
            elif "CHAR_INTERVENTIONS" in l:
                cur_field = "interventions"
            elif "CHAR_OUTCOMES" in l: 
                cur_field = "outcomes"
            else:
                print "wtf field is this???"
                pdb.set_trace()

            # grab the study id
            cur_study_id = l.split("in study ")[-1].split(" --")[0]


        elif "target text" in l: 
            in_target_text = True
            cur_target_text = ""

        elif "candidate sentence" in l:
            in_target_text = False
            in_candidate_text = True
            if cur_candidate_text != "":
                output_str.append([cur_study_id, cur_field, cur_target_text, cur_candidate_text])
            cur_candidate_text = ""

        elif in_target_text:
            cur_target_text += l 

        elif in_candidate_text:
            cur_candidate_text += l


    if output_to_file:
        outpath = results_file_path.replace(".txt", ".csv")
        csv_writer = csv.writer(open(outpath, 'wb'))
        csv_writer.writerows(output_str)

    return output_str
