;;; publishing-directory is passed in on the command line.
;;; See the Makefile for an example.

;;; at least get a backtrace
(setq debug-on-error t)

(add-to-list 'load-path "/home/nick/src/emacs/org/org-mode/contrib/lisp")
(add-to-list 'load-path "/home/nick/src/emacs/org/org-mode/lisp")

(require 'org-loaddefs)
(require 'ox)

(add-to-list 'auto-mode-alist '("\\.org\\'" . org-mode))

(setq base-directory "./")
;;; CSS for github
(setq html-head (mapconcat (lambda (x)
                             (format
                              "<link rel=\"stylesheet\" href=\"%s\" type=\"text/css\"/>"
                              x))
                           '("../../stylesheets/normalize.css"
                             "../../stylesheets/stylesheet.css"
                             "../../stylesheets/github-light.css")
                           "\n"))
;;; (setq html-head "")
(setq org-html-postamble-format '(("en" "<p class=\"date\">Page updated: %T</p>\n")))

(setq publishing-subdirs '("agent" "release-notes" "server"))

(defun publishing-entry (project)
  `(,project
    :base-directory ,(concat base-directory project)
    :base-extension "org"
    :publishing-directory ,(concat publishing-directory project)
    :publishing-function org-html-publish-to-html
    :headline-levels 3
    :section-numbers nil
    :with-toc t
    :with-tags nil
    :html-head ,html-head
    :html-preamble t))

(setq org-publish-project-alist
      `(("index"
         :base-directory ,base-directory
         :base-extension "org"
         :include ("index.org")
         :exclude ".*\.org"
         :publishing-directory ,publishing-directory
         :publishing-function org-html-publish-to-html
         :headline-levels 3
         :section-numbers nil
         :with-toc nil
         :with-tags nil
         :html-head ,html-head
         :html-preamble t)
        ,@(mapcar (function publishing-entry) publishing-subdirs)
        ("orgfiles"
         :components ,publishing-subdirs)
        ("pbench-doc"
         :components ("index" "orgfiles" "images"))))

