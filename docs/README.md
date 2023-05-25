# Documentation

PBench website [gh-pages](https://distributed-system-analysis.github.io/pbench)
PBench readthedocs [self hosted](https://distributed-system-analysis.github.io/pbench/docs) and [readthedoc instance](https://pbench.readthedocs.io) 

This dir has all the pbench documentation(api, user guide, commands, gh-pages, etc).
Pbench website is hosted on gh-pages and readthedocs pages(`/docs`) are also hosted along with it.

## Readthedocs setup

```console
$ pip3 install -r requirement.txt
$ make clean
$ make html
```

> **Note:**  Above command will build your static readthedocs page/website in `_build/html` dir.

## Some important links

- [online markdown editor](https://pandao.github.io/editor.md/en.html)
- [myst-parser](https://myst-parser.readthedocs.io/en/latest/syntax/optional.html) is a plugin used to build our markdown documentation.
