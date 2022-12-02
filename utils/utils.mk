#
# Utility widgets for makefiles
#
# This file is intended to be included into other makefiles.  It provides useful
# devices of various sorts which are applicable to a variety of situations.
#


# Compose lists of potential distro-version strings with versions 0-99
# (e.g., `_ALL_centos_VERSIONS` including "centos-7", "centos-8", "centos-9",
# `_ALL_fedora_VERSIONS` including "fedora-32", "fedora-33", and "fedora-34",
# `_ALL_rhel_VERSIONS` including "rhel-7", "rhel-8", and "rhel-9", and
# `_DISTROS` concatenating the contents of all the lists) which can be used to
# drive pattern matching on distro-based target rules.
_DIGITS := 0 1 2 3 4 5 6 7 8 9
_NUMBERS := $(patsubst 0%,%,$(foreach tens,${_DIGITS},$(foreach ones,${_DIGITS},${tens}${ones})))
_ALL_DISTRO_NAMES := centos fedora rhel
_ADV_TMPL = _ALL_${d}_VERSIONS := $(foreach v,${_NUMBERS},${d}-${v}) # template for setting version lists
$(foreach d,${_ALL_DISTRO_NAMES},$(eval $(call _ADV_TMPL, ${d})))  # set _ALL_centos_VERSIONS, etc.
_DISTROS := $(foreach d,${_ALL_DISTRO_NAMES},${_ALL_${d}_VERSIONS})

# In Make, it is hard to refer to a single blank or space character.  This pair
# of definitions does that:  create a definition which is literally empty, and
# then use that as a delimiter around a space character, and viola.
_empty:=
_space:= ${_empty} ${_empty}

# This is a "function" which is intended to produce a sequence number managed in
# the specified file.  If the file does not exist, the function returns 1;
# otherwise, it reads the current value from the file, increments it, writes it
# back to the file, and returns the originally read number.
get_sequence_number = $(shell \
	s=1 ; \
	if [[ -e $(1) ]] ; then \
	  s=$$(< $(1)) ; \
	  echo $$((s+1)) >$(1) ; \
	fi ; \
	echo $$s )
