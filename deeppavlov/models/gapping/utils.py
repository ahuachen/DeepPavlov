import bisect

import numpy as np

from deeppavlov import build_model
from deeppavlov.core.commands.utils import parse_config
from deeppavlov.models.morpho_tagger.common import make_pos_and_tag


HYPHENS = "-—–"
QUOTES = "«“”„»``''\""


def tokens_to_indexes(token_starts, char_index):
    if isinstance(char_index, (list, tuple)):
        token_starts = [tokens_to_indexes(token_starts, x) for x in char_index]
        return token_starts
    return bisect.bisect_left(token_starts, char_index)

def _make_token_starts(text, words):
    starts = []
    start = 0
    for word in words:
        while not text[start:].startswith(word):
            if text[start] in QUOTES and word in QUOTES:
                break
            start += 1
        starts.append(start)
        start += len(word) if word not in QUOTES else 1
    assert len(starts) == len(words)
    return starts


class CharToWordIndexer:

    def __init__(self):
        pass

    def __call__(self, texts, tokens, indexes):
        token_starts = [_make_token_starts(sent, sent_tokens)
                        for sent, sent_tokens in zip(texts, tokens)]
        answer = [tokens_to_indexes(*elem) for elem in zip(token_starts, indexes)]
        return answer


def is_verb(tag, word=None):
    pos, feats = make_pos_and_tag(tag, return_mode="dict")
    if pos == "ADJ" or (pos == "VERB" and feats.get("VerbForm") == "Part"):
        return feats.get("Variant") in ["Short", "Brev"]
    else:
        if word.lower() in ["можно", "надо", "нужно", "нельзя"]:
            return True
        return pos in ["VERB", "AUX"]

class VerbSelector:

    def __init__(self, config_path):
        config = parse_config(config_path)
        config["chainer"]["pipe"].pop()
        config["chainer"]["out"] = ["y_predicted"]
        self.model = build_model(config)

    def __call__(self, data):
        tag_data = self.model(data)
        answer = [[] for _ in data]
        for i, elem in enumerate(tag_data):
            for j, tag in enumerate(elem):
                if is_verb(tag, data[i][j]):
                    answer[i].append(j)
        return answer

class GappingSourceTransformer:

    def __init__(self, only_first=True, only_starts=True):
        self.only_first = only_first
        self.only_starts = only_starts

    def __call__(self, sents, gap_data, verb_indexes):
        L = max(len(x) for x in sents)
        if not self.only_first or not self.only_starts:
            raise NotImplementedError("Not implemented yet.")
        answer = [np.zeros(shape=(len(elem), L), dtype=int) for elem in verb_indexes]
        for i, sent_verbs in enumerate(verb_indexes):
            verb_indexes = {verb: index for index, verb in enumerate(sent_verbs)}
            curr_gap_verb_data, curr_gap_data = gap_data[i][:2]
            if len(curr_gap_verb_data) == 0:
                continue
            gap_verb = curr_gap_verb_data[0][0]
            gap_verb_index = verb_indexes.get(gap_verb)
            if gap_verb_index is None:
                continue
            for curr_gap, _ in curr_gap_data:
                answer[i][gap_verb_index, curr_gap] = 1
        return answer
