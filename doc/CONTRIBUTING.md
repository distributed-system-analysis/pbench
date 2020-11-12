# Guidelines for Contributing to Pbench

## 1. Forking the repository:

![Image](https://lh3.googleusercontent.com/qzbrO61ihlrw1uZUzY-oUBV0z2AX2nQhB9mvvo_27WHMEuF1CkElqEUTTW01YJqPBaJTyT_DfPRqXAIfXetNB7yEr1foW2Q79RLgqfw-rnNlx2ZyX3gydY3Dr4xoInckbcevTq_7)

Forking a repository allows you to freely experiment with changes without affecting the original project. Most commonly, forks are used to either propose changes to someone else's project or to use someone else's project as a starting point for your own idea.

## 2. Cloning

Cloning is used to create a local copy of the repository. It takes only one command in the terminal to clone the repository.
```
git clone https://github.com/distributed-system-analysis/pbench.git
```

## 3. Choosing an issue to work upon

1. Go to the issues section, to find a list of open issues.

![Image](https://lh6.googleusercontent.com/4d5CY0nB21_T6iSwLDLUw2voFDPbm3miipC4vthubhUoiipTrVnqHx3vBTIqHyaOdhyUR4Xbc-OV6AXw-BSpla2QnT6EahvzQzJKm42NQn9R0AYocjA50VfPAKRCAIFmNya6IY0e)

1. Select the issues you are interested to work upon based upon the labels and descriptions.

![Image](https://lh5.googleusercontent.com/W8IFbEHd56Ykese8OPVV8eMuakkYIO-N2XjeGSY6L3Mysr2p9-K7BMV6sh4ZJDfm1vrycqvWMflL4nx_36zUEHcZ4kgbbP5a1BHOburE8st3IuQhwIF8eq2y8Cix__E1sMGs13gj)

1. It is a good practice to assign the issue to yourself to let others know you're working upon it.

![Image](https://lh6.googleusercontent.com/MsF7-9lTnDgQsi888PqSFtWCOfoxnhDQVfNv6aem7AcEo06gDrCk-ISZ8C3VIe6AUfRfglRq3xgaHSzS2yfQHutWkbHingQswCYGpBqVOaa_WImECxYvKAZM-i6lr7HirFDAhA41)

## Making changes to the codebase

- Follow the instructions in the README.md to setup and install pbench.
- Save your changes by creating your own local branches on git

## Add, Commit and Push

- Follow these commands to push the changes to your branch.
```
git add .
git commit -m "Issue solved"
git push origin branch_name
```

## Conventions on commits, PRs, and overall git best practices.

- Commit messages should have a short description (50 - 70 characters) followed by a longer format description of the changes below if needed. You’ll also notice each line is formatted for a specific length in the longer format description. For example:

```
Extend auditing to incoming, results, and users

The server audit is now applied to the incoming, results, and users
directory hierarchies.  Any unpacked tar ball should now be compre-
hensively checked to see that all is in the correct place.

The test-20 unit test gold file holds an example of an audit report
covering all the possible outputs it can emit.  Each unit test runs
the report as well, and they have been updated accordingly.
```

- For more on best practices, check out this article for reference from time to time: https://www.git-tower.com/learn/git/ebook/en/command-line/appendix/best-practices

## Opening a pull request
1. **If there are multiple commits, squash down the commits to one**
  1. For more complicated commits it is appropriate to have more than one
1. Commit the changes
1. Click on New Pull Request
1. Write appropriate Pull Request Title stating the fix
  1. Use present tense (ex. Fixes, Changes, Fixing, Changing..)
1. Reference the issue that the PR is fixing with **“Fixes #issue_number”** in the description
1. Provide a detailed description (at least 50 - 70 characters) of the changes; if UI related, add screenshots or gif
1. Make sure that the branches can be automatically merged (otherwise rebase the PR with `master`) and then click the drop down next to, `Create pull request`, and select `Create draft pull request`
![Image](https://lh5.googleusercontent.com/V14SjFhimKYF1fH6TXMfaoZtDCj2ZH0d9USqe8YHyn0xOOVYekiXtx2CwdOQbSvxWPB6JVEfi4jSM_mjkSMaaI7voQNYQ8gDWntMhzCMbj3wrK3H4eCSEsdVq_XP_aZMdb5h9xU4)

1. Assign the PR to yourself and add appropriate labels
1. Add "**DO NOT MERGE**" label if the work is not needed to be merged or there is no agreement on the work yet
1. Make sure to add Milestone to the PR to mention specific release
1. Request for review once the work is ready for getting reviewed
![Image](https://lh6.googleusercontent.com/iM-vaIsFQ8ew7vpNDUvmSY9MVjyTadTZkngdlQfo7qYe_QQuFSA8yZ_3P40fBdeNw6Q-lSJwDD59jfBoQgdNP3mGHPgrjVicsyGt8QkMMAaDYowHsIyAnukXsEiFPSOnYnrZyze3)
1. Select the `Ready for Review` button to move the PR out of `Draft` mode indicating it is ready for review and merging

## Creating an Isssue
1. Make sure to add proper details to the Issue raised
1. Upload screenshot(if possible) in dashboard issues
1. Apply proper labels to the Issue
1. Make sure to add Milestone and Project to the issue to mention specific release.
1. Try to actively respond to the communication in case of comments in the same issue.

## Reviewing a pull request
1. Go to Files changed and check for the fixes proposed by the Pull Request
1. Check for certain general criteria:
  1. The PR has no merge conflicts with the base branch
  1. The commits are squashed into one
  1. There is proper indentation and alignment
  1. No additional lines are added unnecessarily
  1. The code is clearly understandable, with comments if necessary to clarify
  1. Do not merge the PR with `DO NOT MERGE` or `WIP` label.
1. In case of the requirement of running the changes in the PR on the local system, follow the mentioned process:
  - To fetch a remote PR into your local repo,
```
git fetch origin pull/ID/head:BRANCHNAME
where ID is the pull request id and BRANCHNAME is the name of the new branch that you want to create. Once you have created the branch, then simply
git checkout BRANCHNAME
```
  - If modification is required, then either “Request changes” or add “General comments” for your feedback

  - For more information about reviewing PR in github go through:
https://help.github.com/en/articles/about-pull-request-reviews
https://help.github.com/en/articles/reviewing-proposed-changes-in-a-pull-request
