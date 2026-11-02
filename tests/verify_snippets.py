#!/usr/bin/env python3
"""Compile the actual Markdown snippets and run regression checks (C++17).

Usage: python3 tests/verify_snippets.py [--sanitize]
Set CXX to choose a compiler. All generated files live in a temporary directory.
"""

import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ALGORITHMS = (ROOT / '算法/算法.md').read_text()
STRUCTURES = (ROOT / '数据结构/数据结构.md').read_text()


def section(document, start, end=None):
    text = document[document.index(start):]
    return text[:text.index(end)] if end else text


def blocks(text):
    return re.findall(r'^\s*```cpp\s*\n(.*?)^\s*```\s*$', text, re.M | re.S)


def first(document, start, end):
    return blocks(section(document, start, end))[0]


HEADERS = '''
#include <algorithm>
#include <atomic>
#include <cassert>
#include <climits>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <functional>
#include <iostream>
#include <list>
#include <memory>
#include <mutex>
#include <numeric>
#include <queue>
#include <random>
#include <sstream>
#include <stack>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>
using namespace std;
'''


def generate_source():
    units = []
    calls = []

    def add(name, code, checks):
        # Headers belong outside namespaces; the test harness supplies them above.
        code = re.sub(r'^\s*#include[^\n]*', '', code, flags=re.M)
        units.append(f'namespace {name} {{\n{code}\nvoid verify() {{\n{checks}\n}}\n}}')
        calls.append(f'{name}::verify(); cout << "PASS {name}\\n";')

    sort_section = section(ALGORITHMS, '## 排序算法', '### 6. 排序算法')
    sorting = '\n'.join(blocks(sort_section))
    add('sorting', sorting, r'''
mt19937 rng(7);
for (int n = 0; n <= 50; ++n) for (int trial = 0; trial < 30; ++trial) {
    vector<int> values(n);
    for (auto& v : values) v = int(rng() % 11) - 5;
    auto expected = values;
    std::sort(expected.begin(), expected.end());
    auto v = values; bubble_sort(v); assert(v == expected);
    v = values; selectSort(v); assert(v == expected);
    v = values; quick_sort(v.data(), 0, n - 1); assert(v == expected);
    v = values; vector<int> tmp(n); mergeSort(v, tmp, 0, n - 1); assert(v == expected);
    v = values; assert(sortArray(v) == expected);
    for (int k = 1; k <= n; ++k) {
        v = values; assert(quick_sort(v.data(), 0, n - 1, k) == expected[k - 1]);
        v = values; Solution s; assert(s.findKthLargest(v, k) == expected[n - k]);
    }
}
''')
    binary = first(ALGORITHMS, '### 1. 整数二分', '### 2. 浮点型二分')
    # Provide the problem-specific monotone predicate omitted by the template.
    for name, predicate, checks in [
        ('binary_lower', 'return x >= threshold;', 'assert(bsearch_1(INT_MIN, INT_MAX) == threshold);'),
        ('binary_upper', 'return x <= threshold;', 'assert(bsearch_2(INT_MIN, INT_MAX) == threshold);'),
    ]:
        code = binary.replace('bool check(int x) {/* ... */}', f'int threshold;\nbool check(int x) {{{predicate}}}')
        add(name, code, 'for (int t : {INT_MIN, -1, 0, 1, INT_MAX}) {threshold = t;' + checks + '}')
    bit_blocks = blocks(section(ALGORITHMS, '### 1. 常用技巧', '### 2. `n &'))
    add('bits', '', 'uint32_t x = 0x80000001U, num = x; int cnt[32] = {};\n' + '\n'.join(bit_blocks) + '\nassert(cnt[0] == 1 && cnt[31] == 1 && s == 31 && count == UINT32_MAX);')
    lowbit = first(ALGORITHMS, '### 3. `lowbit(x)`', '## 快速幂')
    add('low_bits', lowbit[:lowbit.index('uint32_t a =')], 'assert(lowbit(0) == 0); assert(lowbit(40) == 8); assert(lowbit(0x80000000U) == 0x80000000U);')
    power = first(ALGORITHMS, '## 快速幂', '## 深度优先搜索')
    add('power', power, r'''
assert(quick_pow(2, 0, 1) == 0);
assert(quick_pow(4000000000LL, 2, 7) == 2);
for (long long a : {LLONG_MIN, -11LL, 0LL, 3LL, LLONG_MAX})
    for (int p : {1, 2, 7, INT_MAX}) {
        long long expected = 1 % p, base = a % p;
        if (base < 0) base += p;
        for (int b = 0; b <= 30; ++b) {
            assert(quick_pow(a, b, p) == expected);
            expected = expected * base % p;
        }
    }
bool threw = false; try { quick_pow(2, -1, 7); } catch (const invalid_argument&) { threw = true; } assert(threw);
threw = false; try { quick_pow(2, 2, 0); } catch (const invalid_argument&) { threw = true; } assert(threw);
''')
    for name, heading, end, checks in [
        ('dfs_void', '#### 1) 无返回值的网格深搜框架', '#### 2)有返回值', 'dfs(grid,0,0); assert(grid[0][0] == 2 && grid[1][1] == 2); dfs(empty,0,0);'),
        ('dfs_area', '#### 2)有返回值的深搜框架', '## 广度优先搜索', 'assert(dfs(grid,0,0) == 4); assert(dfs(empty,0,0) == 0);'),
    ]:
        add(name, first(ALGORITHMS, heading, end), 'vector<vector<int>> grid={{1,1,0},{0,1,1},{1,0,0}}, empty;\n'+checks)
    mod = first(ALGORITHMS, '### 1. 求模%', '## 前缀和和差分')
    add('modulo', mod, 'assert(normalized_mod(-5, 3) == 1); assert(normalized_mod(LLONG_MIN, LLONG_MAX) == LLONG_MAX - 1);')
    add('strings', first(STRUCTURES, '#### string类的实现', '### 字符串函数的实现'), r'''
String a("hello"), b(std::move(a)), c(a), d;
assert(string(a.get_c_str()).empty() && string(b.get_c_str()) == "hello");
d = a; assert(string(d.get_c_str()).empty());
c = b; c = c; assert(string(c.get_c_str()) == "hello");
a = b; assert(string(a.get_c_str()) == "hello");
ostringstream os; os << d << b; assert(os.str() == "hello");
''')
    char_functions = '\n'.join(blocks(section(STRUCTURES, '### 字符串函数的实现', '### `KMP`算法')))
    add('char_functions', char_functions, r'''
char buf[32]; assert(char_functions::strcpy(buf, "abc") == buf);
assert(string(buf) == "abc"); char_functions::strcat(buf, "def");
assert(string(buf) == "abcdef" && char_functions::strlen(buf) == 6);
char hi[] = {char(0xff), 0}, lo[] = {char(1), 0};
assert(char_functions::strcmp(hi, lo) > 0);
for (int src = 0; src < 8; ++src) for (int dst = 0; dst < 8; ++dst)
    for (int len = 0; len <= 8; ++len) {
        char actual[16] = "0123456789abcde", expected[16];
        std::memcpy(expected, actual, sizeof(actual));
        std::memmove(expected + dst, expected + src, len);
        assert(Memcpy(actual + dst, actual + src, len) == actual + dst);
        assert(std::memcmp(actual, expected, sizeof(actual)) == 0);
    }
assert(Memcpy(nullptr, nullptr, 0) == nullptr);
''')
    tree = first(STRUCTURES, '##### 层序构造和打印', '### 红黑树')
    add('binary_tree', tree[:tree.index('int main()')], r'''
vector<int> empty, a={1,2}, sparse={1,-1,2,9,9,3};
assert(build_binary_tree(empty) == nullptr);
auto root = build_binary_tree(a); assert(root->left && root->left->val == 2 && !root->right); destroy_binary_tree(root);
root = build_binary_tree(sparse); assert(!root->left && root->right->left->val == 3); destroy_binary_tree(root);
''')
    add('trie', first(STRUCTURES, '### 字典树`Trie`', '##  哈希表'), r'''
Trie t; t.insert("apple"); assert(t.find("apple")); assert(!t.find("app"));
t.insert("app"); assert(t.find("app")); assert(!t.find("apples"));
assert(!t.find("")); t.insert(""); assert(t.find(""));
''')
    priority_blocks = blocks(section(STRUCTURES, '### `priority_queue`', '#### 常用操作函数'))
    add('priority_comparators', '\n'.join(priority_blocks[1:4]), r'''
priority_queue<tmp1, vector<tmp1>, tmp2> functor;
for(int x : {1, 3, 2}) {functor.push(tmp1(x)); q.push(tmp1(x));}
assert(functor.top().x == 3 && q.top().x == 3);
''')
    topology = first(STRUCTURES, '### 拓扑排序', '### 并查集')
    names = iter(['CourseCheck', 'CourseOrder', 'Reconstruction'])
    topology = re.sub(r'class Solution', lambda match: 'class ' + next(names), topology)
    add('topology', topology, r'''
vector<vector<int>> prerequisites={{1,0}};
CourseCheck c; assert(c.canFinish(2,prerequisites));
CourseOrder o; assert(o.findOrder(2,prerequisites)==vector<int>({0,1}));
prerequisites.push_back({0,1}); assert(!c.canFinish(2,prerequisites)); assert(o.findOrder(2,prerequisites).empty());
Reconstruction r; vector<int> org={1,2,3}; vector<vector<int>> seqs={{1,2},{2,3}};
assert(r.sequenceReconstruction(org,seqs)); seqs={{1,2},{1,3}}; assert(!r.sequenceReconstruction(org,seqs));
''')
    add('segment_tree', first(STRUCTURES, '### 线段树的代码', '## 图论'), r'''
mt19937 rng(9); vector<int> a(37); SegmentTree tree(a);
for (int step=0; step<2000; ++step) {
    int i=rng()%a.size(), v=int(rng()%2001)-1000; a[i]=v; tree.update(i,v);
    int l=rng()%a.size(), r=rng()%a.size(); if(l>r) std::swap(l,r);
    assert(tree.sumRange(l,r) == accumulate(a.begin()+l,a.begin()+r+1,0LL));
}
vector<int> large={INT_MAX,INT_MAX}; SegmentTree wide(large); assert(wide.sumRange(0,1)==2LL*INT_MAX);
SegmentTree empty({}); assert(empty.sumRange(0,-1) == 0);
bool threw=false; try {empty.update(0,1);} catch(const out_of_range&){threw=true;} assert(threw);
threw=false; try {tree.sumRange(-1,2);} catch(const out_of_range&){threw=true;} assert(threw);
''')
    add('dsu', first(STRUCTURES, '### 并查集', '### 图\n'), 'DSU d(4); d.unite(0,1); d.unite(1,2); d.unite(0,2); assert(d.connected(0,2)); assert(!d.connected(0,3)); assert(d.count() == 2);')
    naive = blocks(section(STRUCTURES, '##### 朴素Dijkstra算法', '##### 堆优化的Dijkstra算法'))[-1]
    add('dijkstra', naive, r'''
Solution s; vector<vector<int>> a={{1,2,10}}, empty;
assert(s.networkDelayTime(a,2,1)==10); assert(s.networkDelayTime(empty,1,1)==0); assert(s.networkDelayTime(empty,2,1)==-1);
vector<vector<int>> sample={{2,1,1},{2,3,1},{3,4,1}}; assert(s.networkDelayTime(sample,4,2)==2);
''')
    heap_blocks = blocks(section(STRUCTURES, '##### 堆优化的Dijkstra算法', '总结:'))
    add('heap_dijkstra', heap_blocks[0], 'Solution s; vector<vector<int>> a={{2,1,1},{2,3,1},{3,4,1}}, empty; assert(s.networkDelayTime(a,4,2)==2); assert(s.networkDelayTime(empty,2,1)==-1);')
    add('effort_path', heap_blocks[1], 'Solution s; vector<vector<int>> a={{1,2,2},{3,8,2},{5,3,5}}; assert(s.minimumEffortPath(a)==2);')
    add('maze', heap_blocks[2], r'''
Solution s; vector<vector<int>> a={{0,0,1,0,0},{0,0,0,0,0},{0,0,0,1,0},{1,1,0,1,1},{0,0,0,0,0}};
vector<int> start={0,4}, end={4,4}; assert(s.shortestDistance(a,start,end)==12);
end={3,2}; assert(s.shortestDistance(a,start,end)==-1);
a={{0}}; start={0,0}; end={0,0}; assert(s.shortestDistance(a,start,end)==0);
a={{0,0,0}}; end={0,2}; assert(s.shortestDistance(a,start,end)==2);
end={0,1}; assert(s.shortestDistance(a,start,end)==-1);
a={{0},{0},{0}}; start={2,0}; end={0,0}; assert(s.shortestDistance(a,start,end)==2);
''')
    mst = first(STRUCTURES, '##### `Kruskal`算法', '## 常考数据结构设计')
    city, points = mst.split('//1584---连接所有点的最小费用')
    add('kruskal_city', city, 'Solution s; vector<vector<int>> a={{1,2,5},{1,3,6},{2,3,1}}; assert(s.minimumCost(3,a)==6); a={{1,2,1}}; assert(s.minimumCost(3,a)==-1);')
    add('kruskal_points', points, 'Solution s; vector<vector<int>> a={{0,0},{2,2},{3,10},{5,2},{7,0}}; assert(s.minCostConnectPoints(a)==20);')
    smart = first(STRUCTURES, '### 智能指针`share_ptr`', '### `LRU`')
    add('smart_ptr', smart.replace('int main()', 'int sample_main()'), 'assert(sample_main()==0); SmartPtr<int> p(new int(3)); p=p; SmartPtr<int> q(p); assert(*q==3);')
    add('lru', first(STRUCTURES, '### `LRU`', '### 写三个线程'), r'''
LRUCache empty(0); empty.put(1,1); assert(empty.get(1)==-1);
LRUCache c(2); c.put(1,1); c.put(2,2); assert(c.get(1)==1); c.put(3,3); assert(c.get(2)==-1);
c.put(4,4); assert(c.get(1)==-1 && c.get(3)==3 && c.get(4)==4); c.put(4,9); assert(c.get(4)==9);
''')
    singleton = first(STRUCTURES, '### 写单例模式', '### 实现一个`mutex`')
    spin = first(STRUCTURES, '### 实现一个`mutex`', None)
    add('concurrency', singleton + spin, r'''
SpinLock lock; int total=0; vector<Singleton*> instances(8); vector<thread> threads;
for(int t=0;t<8;++t) threads.emplace_back([&,t]{
    instances[t]=&Singleton::getInstance();
    for(int i=0;i<10000;++i) {lock_guard<SpinLock> guard(lock); ++total;}
});
for(auto& t:threads) t.join();
assert(total==80000); for(auto p:instances) assert(p==instances[0]);
''')
    return HEADERS + '\n'.join(units) + '\nint main(){\n' + '\n'.join(calls) + '\n}\n', len(calls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sanitize', action='store_true', help='Enable AddressSanitizer and UBSan')
    args = parser.parse_args()
    source, count = generate_source()
    with tempfile.TemporaryDirectory(prefix='algorithm-notes-test-') as directory:
        path = Path(directory)
        cpp = path / 'snippets.cpp'
        executable = path / 'verify'
        cpp.write_text(source)
        command = shlex.split(os.environ.get('CXX', 'c++')) + ['-std=c++17', '-pthread', '-O1', '-g']
        if args.sanitize:
            command += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        subprocess.run(command + [str(cpp), '-o', str(executable)], check=True, timeout=120)
        subprocess.run([str(executable)], check=True, timeout=60)
    print(f'All {count} snippet groups passed.')


if __name__ == '__main__':
    main()
