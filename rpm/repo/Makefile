# make sure we can get to configtools.py even if configtools is not installed
# or if an older, less capable version is installed.
desthost = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repohost repo)
destuser = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repouser repo)
destdir  = $(shell PYTHONPATH=${TOP}/configtools/build/lib:$$PYTHONPATH PATH=${TOP}/configtools/build/bin:$$PATH getconf.py repodir repo)

push:
	rsync -ave ssh ./pbench.repo ${destuser}@${desthost}:${destdir}/yum.repos.d

test:
	@echo "desthost=\"${desthost}\""
	@echo "destuser=\"${destuser}\""
	@echo "destdir=\"${destdir}\""
