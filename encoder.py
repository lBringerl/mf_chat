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
        yield f'__#{self._counter}__'
        counter += 1

    def _create_encoding_mapping(self, tokens: Iterable[str]) -> dict:
        mapping = {}
        for key, token in zip(self.gen_key(), tokens):
            mapping[key] = token
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
        _, table = match
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
        tokens = data.split(' ')
        for i, token in enumerate(tokens):
            tokens[i] = self._encoding_mapping.get(token, token)
        return ' '.join(tokens)

    def decode(self, data: str) -> str:
        # TODO: Must work in pair with decode. If mapping is changed, decode
        # should't be called
        tokens = data.split(' ')
        for i, token in enumerate(tokens):
            tokens[i] = self._decoding_mapping.get(token, token)
        return ' '.join(tokens)
