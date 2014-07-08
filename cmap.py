import time
import sys
from collections import defaultdict

import dateutil.parser
import svgwrite


MAX_W = 1300.0
MAX_H = 650.0
PADDING = 50
GRID_SIZE = 100
NUM_VBUCKETS = 1024
H = MAX_H / NUM_VBUCKETS


def memodict(f):
    class Memodict(dict):
        def __missing__(self, key):
            ret = self[key] = f(key)
            return ret
    return Memodict().__getitem__


@memodict
def get_datetime(line):
    datetime = line.strip().split(',')[1]
    datetime = dateutil.parser.parse(datetime)
    return time.mktime(datetime.timetuple()) * 10 ** 3 + \
        datetime.microsecond / 10 ** 3  # ms


class Parser(object):

    def __init__(self):
        self.compactions = defaultdict(list)
        self.reb_starts = []
        self.reb_ends = []
        self.first = float('inf')
        self.last = 0

    def parse(self, filename):
        with open(filename) as fh:
            for line in fh:
                if 'master' in line:
                    continue

                if 'Started rebalancing bucket' in line:
                    self.reb_starts.append(get_datetime(line))
                    self.first = min(self.first, get_datetime(line))
                    self.last = max(self.last, get_datetime(line))
                elif 'Rebalance completed successfully' in line:
                    self.reb_ends.append(get_datetime(line))
                    self.first = min(self.first, get_datetime(line))
                    self.last = max(self.last, get_datetime(line))
                elif ('maybe_compact_vbucket' in line
                        or 'spawn_vbucket_compactor' in line) \
                        and 'from' not in line \
                        and 'initial call' not in line:

                    self.first = min(self.first, get_datetime(line))
                    self.last = max(self.last, get_datetime(line))

                    if 'Compacting' in line:
                        b = int(
                            line
                            .strip()
                            .split()[-1]
                            .replace('<', '')
                            .replace('>', '')
                            .strip('"')
                            .split('/')[-1]
                        )
                        self.compactions[b].append(get_datetime(line))


class Drawer(object):

    def __init__(self, first, last):
        self.dwg = svgwrite.Drawing(filename='compaction.svg')
        self.first = first
        self.last = last

    def save(self):
        self.dwg.save()

    def scale(self, datetime):
        return int(MAX_W * (datetime - self.first) / (self.last - self.first))

    def create_canvas(self):
        rect = self.dwg.rect(
            (PADDING / 2, PADDING / 2),
            (MAX_W + 1, MAX_H),
            fill='white',
            stroke='black',
            shape_rendering='crispEdges',
        )
        self.dwg.add(rect)

    def add_grid(self):
        for g in range(PADDING / 2, int(MAX_W), GRID_SIZE):
            line = self.dwg.line(
                (g, PADDING / 2),
                (g, MAX_H + PADDING / 2),
                stroke='black',
                stroke_dasharray='5,5',
                shape_rendering='crispEdges',
            )
            self.dwg.add(line)

    def add_compaction(self, datetime, vb):
        rect = self.dwg.rect(
            (PADDING + self.scale(datetime), PADDING / 2 + H * vb),
            (H * 4, H),
            fill='#F89406',
            stroke_width=0,
        )
        self.dwg.add(rect)

    def add_reb_start(self, datetime):
        line = self.dwg.line(
            (PADDING + self.scale(datetime), PADDING / 2),
            (PADDING + self.scale(datetime), MAX_H + PADDING / 2),
            stroke='#DE1B1B',
            stroke_width=2,
        )
        self.dwg.add(line)

    def add_reb_end(self, datetime):
        line = self.dwg.line(
            (PADDING + self.scale(datetime), PADDING / 2),
            (PADDING + self.scale(datetime), MAX_H + PADDING / 2),
            stroke='#118C4E',
            stroke_width=2,
        )
        self.dwg.add(line)


def main():
    parser = Parser()
    parser.parse(filename=sys.argv[-1])

    drw = Drawer(parser.first, parser.last)
    drw.create_canvas()
    drw.add_grid()

    for vb in sorted(parser.compactions):
        for datetime in parser.compactions[vb]:
            drw.add_compaction(datetime, vb)

    for reb_start in parser.reb_starts:
        drw.add_reb_start(reb_start)

    for reb_end in parser.reb_ends:
        drw.add_reb_end(reb_end)

    drw.save()


if __name__ == '__main__':
    main()
