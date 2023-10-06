import re
from typing import Dict, Iterable, Optional, Set


class SimpleEncoder:

    def __init__(self, description_file: Optional[str] = None):
        self._table_pattern = re.compile('"([\w.]+)":$')
        self._column_pattern = re.compile('-\s([\w\d_]+)\s')
        self._encoding_mapping = {}
        self._decoding_mapping = {}
        if description_file:
            self.reload_description(description_file)
    
    def reload_description(self, filename: str):
        tokens = self._parse_file(filename)
        self._encoding_mapping = self._create_encoding_mapping(tokens)
        self._decoding_mapping = self._create_decoding_mapping(
            self._encoding_mapping
        )
    
    def gen_key(self, counter=0):
        while 1:
            yield f'__#{counter}__'
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
        
    def _parse_file(self, filename: str) -> Set[str]:
        tokens = set()
        with open(filename, 'r') as f:
            data = f.read()
        descriptions = data.split('\n\n')
        for desc in map(str.strip, descriptions):
            if desc:
                tokens |= self._parse_description(desc)
        return tokens

    def _parse_description(self, data: str) -> Set[str]:
        tokens = set()
        lines = data.split('\n')
        if len(lines) == 0:
            raise ValueError('Table description is not in appropriate format.'
                             'Couldn\'t find any lines')
        match = self._table_pattern.search(lines[0])
        if not match:
            raise ValueError('Table description is not in appropriate format.'
                             'Couldn\'t find table name in first line')
        table = match[1]
        tokens.add(table)
        if len(lines) < 2:
            raise ValueError('Table description is not in appropriate format.'
                             'No column descriptions were found')
        for line in lines[1:]:
            match = self._column_pattern.search(line)
            if match:
                tokens.add(match[1])
        return tokens

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
        pattern = re.compile('(__#[\d]+__)')
        for i, word in enumerate(words):
            matches = pattern.findall(word)
            if len(matches) == 0:
                continue
            tokens = [t for t in matches if t in self._decoding_mapping.keys()]
            for token in tokens:
                word = word.replace(token, self._decoding_mapping[token])
            words[i] = word
        return ' '.join(words)
