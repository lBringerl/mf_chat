import re
from typing import Dict, Iterable, Tuple

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

    def encode(self, data: str) -> Tuple[str, dict[str, str]]:
        decoding_mapping = {}
        words = data.split(' ')
        pattern = re.compile('([\w\d._]+)')
        for i, word in enumerate(words):
            matches = pattern.findall(word)
            if len(matches) == 0:
                continue
            for match in matches:
                token = match.lower()
                if not token in self._encoding_mapping.keys():
                    continue
                token_encoded = self._encoding_mapping[token]
                decoding_mapping[token_encoded] = decoding_mapping.get(
                    token_encoded, match
                )
                word = word.replace(match, token_encoded)
            words[i] = word
        return ' '.join(words), decoding_mapping

    @staticmethod
    def decode(data: str, decoding_mapping: dict[str, str]) -> str:
        words = data.split(' ')
        pattern = re.compile('(unknown#[\d]+)')
        for i, word in enumerate(words):
            matches = pattern.findall(word)
            if len(matches) == 0:
                continue
            tokens = [t for t in matches if t in decoding_mapping.keys()]
            for token in tokens:
                word = word.replace(token, decoding_mapping[token])
            words[i] = word
        return ' '.join(words)
