from pathlib import Path
import re
from typing import List, Set, Tuple


class DescriptionParserError(Exception):
    pass


class DescriptionParser:

    def __init__(self, description_dir: str):
        self._table_pattern = re.compile('Таблица ([\w.\d]+)$')
        self._column_pattern = re.compile('^([\w\d]+)[\s]*;')
        self._description_dir = Path(description_dir)
        self._tables = dict()
        self._descriptions = dict()
        self.reload_description()

    @property
    def tables(self) -> Set[str]:
        return set(map(str.lower, self._tables.keys()))
    
    def get_table_description(self, table: str) -> str:
        return self._descriptions[table.lower()]
    
    def get_table_columns(self, table: str) -> Tuple[str]:
        return self._tables[table.lower()]
    
    def reload_description(self):
        if not self._description_dir.exists():
            raise DescriptionParserError('Couldn\'t find description dir: '
                                         f'{self._description_dir}')
        for filename in self._description_dir.glob('*.txt'):
            table, columns, desc = self._parse_file(filename)
            self._tables[table] = columns
            self._descriptions[table] = desc

    def _parse_file(self, filename: str) -> Tuple[str, List[str], str]:
        with open(filename, 'r') as f:
            desc = f.read()
        table, columns = self._parse_description(desc.strip())
        return table, columns, desc

    def _parse_description(self, data: str) -> Tuple[str, List[str]]:
        lines = data.split('\n')
        if len(lines) == 0:
            raise ValueError('Table description is not in appropriate format.'
                             'Couldn\'t find any lines')
        match = self._table_pattern.search(lines[0])
        if not match:
            raise ValueError('Table description is not in appropriate format.'
                             'Couldn\'t find table name in first line')
        table = match[1].lower()
        if len(lines) < 2:
            raise ValueError('Table description is not in appropriate format.'
                             'No column descriptions were found')
        columns = []
        for line in lines[1:]:
            match = self._column_pattern.search(line)
            if match:
                columns.append(match[1].lower())
        return table, tuple(columns)
