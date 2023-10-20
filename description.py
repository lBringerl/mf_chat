from pathlib import Path
import re
from typing import Dict, Iterable, Optional, Set


class DescriptionParserError(Exception):
    pass


class DescriptionParser:

    def __init__(self, description_dir: str):
        self._table_pattern = re.compile('"([\w.]+)":$')
        self._column_pattern = re.compile('-\s([\w\d_]+)\s')
        self._description_dir = Path(description_dir)
        self.reload_description()
    
    def reload_description(self, filename: str):
        if not self._description_dir.exists():
            raise DescriptionParserError('Couldn\'t find description dir: '
                                         f'{self._description_dir}')
        tokens = self._parse_file(filename)
        self._encoding_mapping = self._create_encoding_mapping(tokens)
        self._decoding_mapping = self._create_decoding_mapping(
            self._encoding_mapping
        )
        
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
