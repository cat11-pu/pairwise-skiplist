# skiplist

一小套跳表有序索引内核：int 键的有序存储与查找，带按排名取第 k 个、范围扫描、
顺序遍历，以及插入、删除和层高维护。每个新节点的层数由调用方注入的确定性提升源
决定，内核只用 Python 标准库，不依赖随机数，也不做任何 I/O。

## 目录

- skiplist/core.py 跳表内核（LevelSource 提升源、SkipList 索引）
- tests/test_core.py 行为测试

## 运行测试

在项目根目录（本文件所在目录）执行：

    python3 -m unittest discover -s tests -v

全部用例通过时进程退出码为 0。若系统里没有 `python3`，把命令里的 `python3` 换成
`python` 即可（Windows 上常见）。
