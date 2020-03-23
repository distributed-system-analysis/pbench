all:  pbench-agent.html test-rpms.html

everything: all pbench-agent.pdf

%.html:	%.org
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'html)" $<

%.pdf:	%.tex
	latexmk --shell-escape -pdf -xelatex $<

%.tex: %.org
	emacs -batch -l batch-export.el --eval "(batch-org-export-as 'latex)" $<


desthost = $(shell pbench-config repohost $(prog) repo)
destuser = $(shell pbench-config repouser $(prog) repo)
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
