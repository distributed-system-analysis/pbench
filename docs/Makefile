#
# In order to build the `pbench-agent.pdf` you need `latexmk` RPM installed.
#

all:  pbench-agent.html

.PHONY: everything
everything: all pbench-agent.pdf singlehtml

%.html:	%.org batch-export.el
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'html)" $<

%.pdf:	%.tex
	latexmk --shell-escape -pdf -xelatex $<

%.tex: %.org batch-export.el
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'latex)" $<

desthost = $(shell getconf.py repohost $(prog) repo)
destuser = $(shell getconf.py repouser $(prog) repo)
destdir  = /var/www/html
dest = ${destuser}@${desthost}:${destdir}

.PHONY: push-doc
push-doc:	pbench-agent.html
	rsync -ave ssh $< ${dest}/index.html

.PHONY: push-results
push-results:	results.html
	rsync -ave ssh $< ${dest}/$<

.PHONY: push-test-rpms
push-test-rpms:	test-rpms.html
	rsync -ave ssh $< ${dest}/test-repo/$<

.PHONY: push-relnotes
push-relnotes: RELEASE-NOTES.html
	rsync -ave ssh $< ${dest}/doc/$<

#
# Sphinx built documentation (requires `pip3 install --user -r requirements.txt`)
#

# You can set these variables from the command line.
SPHINXOPTS    =
SPHINXBUILD   = sphinx-build
SOURCEDIR     = .
BUILDDIR      = _build

# Build the "html" Sphinx target which is what "Read the Docs" wants.  There are
# other supported targets one could use; see `$(SPHINXBUILD) -M help` for a
# complete list if interested.
.PHONY: html
html:
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS)

.PHONY: clean
clean:
	rm -f *~ *.fdb_latexmk *.fls *.toc *.aux *.log *.out *.xdv
	rm -rf $(BUILDDIR)

.PHONY: veryclean
veryclean:	clean
	rm -f *.html *.pdf *.tex
