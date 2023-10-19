import re
from typing import Dict, Iterable, Set

from description import DescriptionParser


class SimpleEncoder:

    def __init__(self, description_parser: DescriptionParser):
        self._encoding_mapping = {}
        self._decoding_mapping = {}
        self._description_parser = description_parser
        self.reload_mapping()
    
    def reload_mapping(self):
        tokens = set(self._description_parser.tables)
        for table in self._description_parser.tables:
            tokens |= set(self._description_parser.get_table_columns(table))
        self._encoding_mapping = self._create_encoding_mapping(tokens)
        self._decoding_mapping = self._create_decoding_mapping(
            self._encoding_mapping
        )
    
    def gen_key(self, counter=0):
        while 1:
            yield f'unknown#{counter}'
            counter += 1

    def _create_encoding_mapping(self, tokens: Iterable[str]) -> dict:
        mapping = {}
        # key_gen = self.gen_key()
        for key, token in zip(self.gen_key(), tokens):
            mapping[token] = key
        return mapping
    
    def _create_decoding_mapping(
            self,
            encoding_mapping: Dict[str, str]
    ) -> Dict[str, str]:
        mapping = {}
        for k, v in encoding_mapping.items():
            mapping[v] = k
        return mapping

    def encode(self, data: str) -> str:
        # TODO: Must work in pair with decode. If mapping is changed, decode
        # should't be called
        words = data.split(' ')
        pattern = re.compile('([\w\d._]+)')
        for i, word in enumerate(words):
            matches = pattern.findall(word)
            if len(matches) == 0:
                continue
            tokens = [t for t in matches if t in self._encoding_mapping.keys()]
            for token in tokens:
                word = word.replace(token, self._encoding_mapping[token])
            words[i] = word
        return ' '.join(words)

    def decode(self, data: str) -> str:
        # TODO: Must work in pair with decode. If mapping is changed, decode
        # should't be called
        words = data.split(' ')
        pattern = re.compile('(unknown#[\d]+)')
        for i, word in enumerate(words):
            matches = pattern.findall(word)
            if len(matches) == 0:
                continue
            tokens = [t for t in matches if t in self._decoding_mapping.keys()]
            for token in tokens:
                word = word.replace(token, self._decoding_mapping[token])
            words[i] = word
        return ' '.join(words)
