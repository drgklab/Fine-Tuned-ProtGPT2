#!/usr/bin/env python
#
# Load generated sequences and call amino acid changes from reference
#

import os
import sys
from functools import reduce
from Bio import Align
import numpy as np
import pandas as pd
import plotnine as pn
import seaborn as sns
import matplotlib.pyplot as plt
import re

from collections import defaultdict

################################################################################
## Build Output Scaffolding
################################################################################

os.makedirs('./calc', exist_ok=True)
os.makedirs('./fig', exist_ok=True)

################################################################################
## Load Reference Sequence
################################################################################

with open('./data/sars_wild.fasta') as f:
    metadata = f.readline().rstrip()
    refseq = ''.join([line.replace('\n', '') for line in f])

################################################################################
## Align Generated Sequences
################################################################################

aligner = Align.PairwiseAligner()
aligner.substitution_matrix = Align.substitution_matrices.load('BLOSUM62')
aligner.open_gap_score = -2

REFSEQ_START = 426
REFSEQ_STOP = 515

LINEAR_PATH = ((0,0), (REFSEQ_STOP-REFSEQ_START, REFSEQ_STOP-REFSEQ_START))

def check_alignment_substitutions(x):
    subs = filter(lambda x: x != '', 
        map(lambda i: (''.join([x.target[i], str(REFSEQ_START + i + 1), x.query[i]])
            if x.target[i] != x.query[i]
            else ''), range(len(x.query))))
    return list(subs)


all_substitutions_predict_dict = defaultdict(int)

with open('./calc/generated_rbd_small.txt') as f:
    for line in f:
        s = line.rstrip()
        alignments = aligner.align(refseq[REFSEQ_START:REFSEQ_STOP], s)
        if (len(alignments) == 1) and alignments[0].path == LINEAR_PATH:
            for k in check_alignment_substitutions(alignments[0]):
                all_substitutions_predict_dict[k] += 1


all_substitutions = set(all_substitutions_predict_dict.keys())

# check all alignments from training set

all_substitutions_train_dict = defaultdict(int)

with open('./data/all_train.fasta') as f:
    s = ''
    for line in f:
        if line.startswith('>') and s != '':
            try:
                alignments = aligner.align(
                    refseq[REFSEQ_START:REFSEQ_STOP], s[REFSEQ_START:REFSEQ_STOP])
            except ValueError:
                s = ''
                continue
            if (len(alignments) == 1) and alignments[0].path == LINEAR_PATH:
                for k in check_alignment_substitutions(alignments[0]):
                    all_substitutions_train_dict[k] += 1
            s = ''
            continue
        s = s + line.rstrip()


all_substitutions_train = set(all_substitutions_train_dict.keys())

# check all alignments from test set

all_substitutions_test_dict = defaultdict(int)

with open('./data/all_test.fasta') as f:
    s = ''
    for line in f:
        if line.startswith('>') and s != '':
            try:
                alignments = aligner.align(
                    refseq[REFSEQ_START:REFSEQ_STOP], s[REFSEQ_START:REFSEQ_STOP])
            except ValueError:
                s = ''
                continue
            if (len(alignments) == 1) and alignments[0].path == LINEAR_PATH:
                for k in check_alignment_substitutions(alignments[0]):
                    all_substitutions_test_dict[k] += 1
            s = ''
            continue
        s = s + line.rstrip()


all_substitutions_test = set(all_substitutions_test_dict.keys())

print('===== Variants in the Training Set =====')
print(all_substitutions_train)

print('===== Variants in the Test Set =====')
print(all_substitutions_test)

print('===== Variants in the Predicted Set =====')
print(all_substitutions)

print('===== New Variants in the Test Set that were predicted =====')
new_subs = list(all_substitutions_test.difference(all_substitutions_train))
predicted = list(map(lambda x: x in all_substitutions, new_subs))
np.array(new_subs)[predicted]

print('===== All Variants in the Test or Train Set that were predicted =====')
new_subs = list(all_substitutions_test.union(all_substitutions_train))
predicted = list(map(lambda x: x in all_substitutions, new_subs))
np.array(new_subs)[predicted]

print('===== Novel Variants Predicted =====')
# novel variants predicted by the algorithm
all_substitutions.difference(
    all_substitutions_test
).difference(
    all_substitutions_train
)

all_items = (list(all_substitutions_predict_dict.items())
        + list(all_substitutions_train_dict.items())
        + list(all_substitutions_test_dict.items()))

all_substitution_freqs_df = pd.DataFrame({
    'substitution': [x[0] for x in all_items],
    'frequency': [x[1] for x in all_items],
    'group': ['Predict'] * len(all_substitutions_predict_dict)
             + ['Train'] * len(all_substitutions_train_dict)
             + ['Test'] * len(all_substitutions_test_dict)
})

all_substitution_freqs_df.to_csv('./calc/merged_substitution_info.csv', index=False)

################################################################################
## Generate Plots
################################################################################

####
# Variant location along primary amino acid sequence density plot
####

subs_dict = {
    'train': all_substitutions_train,
    'test': all_substitutions_test,
#    'only_test': all_substitutions_test.difference(all_substitutions_train),
#    'only_train': all_substitutions_train.difference(all_substitutions_test),
    'predict': all_substitutions
}

df_dicts = []
for k,v in subs_dict.items():
    df_dicts += [{'group':k, 'value':int(x[1:-1])} for x in v]

plot_df = pd.DataFrame(df_dicts)

sns.displot(data=plot_df.loc[plot_df['value'] >= REFSEQ_START + 10,:],
            x='value',
            hue='group',
            kind='kde',
            common_norm=False,
            fill=True,
            palette=sns.color_palette('colorblind'),
            bw_adjust=0.2)
plt.savefig('./fig/substitution_distribution_density_plot.png')
plt.clf()

####
# Variant Pie Chart
####


substitutions_df = pd.DataFrame({
    'type': 
        ['PREDICTED'] * len(all_substitutions_test.intersection(
                            all_substitutions)) +
        ['NOT_PREDICTED'] * len(all_substitutions_test.difference(
                            all_substitutions))
})
data = substitutions_df.groupby("type")['type'].count()
data.plot.pie(autopct="%.1f%%", explode=[0.05]*2, colors=sns.color_palette('colorblind'))
plt.savefig('./fig/test_substitutions_pie_chart.png')
plt.clf()


substitutions_df = pd.DataFrame({
    'type': 
        ['PREDICTED'] * len(all_substitutions_train.intersection(
                            all_substitutions)) +
        ['NOT_PREDICTED'] * len(all_substitutions_train.difference(
                            all_substitutions))
})
data = substitutions_df.groupby("type")['type'].count()
data.plot.pie(autopct="%.1f%%", explode=[0.05]*2, colors=sns.color_palette('colorblind'))
plt.savefig('./fig/train_substitutions_pie_chart.png')
plt.clf()


substitutions_df = pd.DataFrame({
    'type': 
        ['IN_TEST_ONLY'] * len(all_substitutions.intersection(
                            all_substitutions_test.difference(
                            all_substitutions_train))) +
        ['IN_TRAIN_ONLY'] * len(all_substitutions.intersection(
                            all_substitutions_train.difference(
                            all_substitutions_test))) +
        ['IN_TRAIN_AND_TEST'] * len(all_substitutions.intersection(
                            all_substitutions_train.intersection(
                            all_substitutions_test))) +
        ['NOVEL'] * len(all_substitutions.difference(
                            all_substitutions_train.union(
                            all_substitutions_test)))
})
data = substitutions_df.groupby("type")['type'].count()
data.plot.pie(autopct="%.1f%%", explode=[0.05]*4,
             colors=sns.color_palette('colorblind'))
plt.savefig('./fig/predicted_substitutions_pie_chart.png')
plt.clf()

################################################################################
## Generate BLOSUM plots
################################################################################

blosum = Align.substitution_matrices.load('BLOSUM80')

samples = [np.random.choice(
    np.array(range(len(blosum.alphabet)), dtype=int), 2, replace=False)
    for x in range(len(all_substitutions))]


subs_dict = {
    'train': all_substitutions_train,
    'test': all_substitutions_test,
    'predict': all_substitutions,
    'random': [''.join(map(lambda x: blosum.alphabet[x], x)) for x in samples]
}

df_dicts = []
for k,v in subs_dict.items():
    df_dicts += [{'group':k, 'value':blosum[x[0],x[-1]]} for x in v]

plot_df = pd.DataFrame(df_dicts)

sns.boxplot(data=plot_df,
            x='group',
            y='value',
            palette=sns.color_palette('colorblind'),
            showfliers=False)
plt.savefig('./fig/blosum80_boxplot.png')
plt.clf()

blosum = Align.substitution_matrices.load('PAM30')

samples = [np.random.choice(
    np.array(range(len(blosum.alphabet)), dtype=int), 2, replace=False)
    for x in range(len(all_substitutions))]


subs_dict = {
    'train': all_substitutions_train,
    'test': all_substitutions_test,
    'predict': all_substitutions,
    'random': [''.join(map(lambda x: blosum.alphabet[x], x)) for x in samples]
}

df_dicts = []
for k,v in subs_dict.items():
    df_dicts += [{'group':k, 'value':blosum[x[0],x[-1]]} for x in v]

plot_df = pd.DataFrame(df_dicts)

sns.boxplot(data=plot_df,
            x='group',
            y='value',
            palette=sns.color_palette('colorblind'),
            showfliers=False)
plt.savefig('./fig/pam30_boxplot.png')
plt.clf()

#############
# Save variant calls to output
#############

all_sub_ids = list(all_substitutions.union(
    all_substitutions_test.union(
        all_substitutions_train
    )
))

variant_meta_df = pd.DataFrame({
    'Mutation': all_sub_ids,
    'in_train': [x in all_substitutions_train for x in all_sub_ids],
    'in_test': [x in all_substitutions_test for x in all_sub_ids],
    'in_predict': [x in all_substitutions for x in all_sub_ids]
})
variant_meta_df['prediction_identity'] = [
    str(variant_meta_df['in_test'][i]) + '|' +
    str(variant_meta_df['in_train'][i]) + '|' +
    str(variant_meta_df['in_predict'][i])
    for i in range(variant_meta_df.shape[0])
]


variant_meta_df['BLOSUM80'] = [Align.substitution_matrices.load('BLOSUM80')[x[0],x[-1]] 
    for x in variant_meta_df['Mutation']]

variant_meta_df['PAM30'] = [Align.substitution_matrices.load('PAM30')[x[0],x[-1]] 
    for x in variant_meta_df['Mutation']]


variant_meta_df.to_csv('./calc/variant_meta_df.csv', index=False)

################################################################################
## Save Substitutions to MutaBind2 Input Format
################################################################################

VALID_SUB = '^[ARNDCQEGHILKMFPSTWYV0-9]*$'

valid_subs = list(filter(lambda x: re.match(VALID_SUB, x), all_substitutions))


###############
# MutaBind2
###############

#
# Tab-delimited:
#
#       Chain | Residue | Mutant
#
# Chain is always "B" (contact surface glycoprotein to ACE2 on PDB structure 7DF4)
#
with open('./calc/mutabind2_7df4.txt', 'w') as f:
    for s in valid_subs:
        print('{}\t{}\t{}'.format('B', s[:-1], s[-1:]), file=f)

#
# Tab-delimited:
#
#       Chain | Residue | Mutant
#
# Chain is always "A" (contact surface glycoprotein to ACE2 on PDB structure 8D8Q)
#
with open('./calc/mutabind2_8d8q.txt', 'w') as f:
    for s in valid_subs:
        print('{}\t{}\t{}'.format('A', s[:-1], s[-1:]), file=f)


###############
# SAAMBE-3D
###############

#
# Space-delimited:
#
#       Chain | Residue | Mutant
#
# Chain is always "B" (contact surface glycoprotein to ACE2 on PDB structure 7DF4)
#
with open('./calc/saambe3d_6moj.txt', 'w') as f:
    for s in valid_subs:
        print('{} {} {} {}'.format('E', str(int(s[1:-1])), s[0], s[-1:]), file=f)

#
# Space-delimited:
#
#       Chain | Residue | Mutant
#
# Chain is always "A" (contact surface glycoprotein to ACE2 on PDB structure 8D8Q)
#
# Chain A : Spike Glycoprotein
# Chain B : 2196 Light Chain
# Chain C : 2196 Heavy Chain
# Chain H : 2130 Heavy Chain
# Chain L : 2130 Light Chain
#
#
with open('./calc/saambe3d_8d8q.txt', 'w') as f:
    for s in valid_subs:
        print('{} {} {} {}'.format('A', s[1:-1], s[0], s[-1:]), file=f)


print('All done!')
