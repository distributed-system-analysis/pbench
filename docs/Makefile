all:  pbench-agent.html test-rpms.html

everything: all pbench-agent.pdf help

%.html:	%.org
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'html)" $<

%.pdf:	%.tex
	latexmk --shell-escape -pdf -xelatex $<

%.tex: %.org
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'latex)" $<

desthost = $(shell getconf.py repohost $(prog) repo)
destuser = $(shell getconf.py repouser $(prog) repo)
destdir  = /var/www/html
dest = ${destuser}@${desthost}:${destdir}

push-doc:	pbench-agent.html
	rsync -ave ssh $< ${dest}/index.html

push-results:	results.html
	rsync -ave ssh $< ${dest}/$<

push-test-rpms:	test-rpms.html
	rsync -ave ssh $< ${dest}/test-repo/$<

push-relnotes: RELEASE-NOTES.html
	rsync -ave ssh $< ${dest}/doc/$<

.PHONY: clean veryclean
clean:
	rm -f *~ *.fdb_latexmk *.fls *.toc *.aux *.log *.out

veryclean:	clean
	rm -f *.html *.pdf

#
# Sphinx documentation
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

.PHONY: help Makefile
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)
