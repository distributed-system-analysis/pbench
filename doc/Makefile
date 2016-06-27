publish-dest = ./
# testing
# publish-internal-dest = ${HOME}/tmp/pbench/doc/internal/
# publish-external-dest = ${HOME}/tmp/pbench/doc/external/

publish:
	emacs -batch --eval '(setq publishing-directory "${publish-dest}")'\
	      --load pbench-doc.el --eval '(org-publish "pbench-doc" t)'

.PHONY: clean
SUBDIRS = agent release-notes server

clean:
	-for d in ${SUBDIRS}; do\
		cd ./$$d &&\
		rm -f *~ *.fdb_latexmk *.fls *.toc *.aux *.log *.out && cd -\
	;done
	rm -f *~

veryclean: clean
	find . -name '*.html' | xargs rm -f


