---
allowed-tools: Bash(gh pr diff:*), Bash(gh pr view:*), Bash(gh pr comment:*), Bash(git diff:*), Bash(git log:*), Task, Read, Glob, Grep
description: Review a pull request and post the review to GitHub (CI/automated use)
---

## Arguments

- `$ARGUMENTS`: The PR number to review

## Your task

Review the specified pull request and post the review as a PR comment on GitHub. This command is designed for CI/automated environments, so it never casts an approving or blocking review itself — a human ratifies the recommendation.

### Step 1: Gather PR context

Get the PR details and diff:
```
gh pr view $ARGUMENTS
gh pr diff $ARGUMENTS
```

### Step 2: Review the code changes

Use the Task tool with `subagent_type: "code-reviewer"` to perform a thorough code review of the changes. Pass the diff and changed files to the agent for analysis.

The code-reviewer agent will analyze:
- Code quality and best practices
- Potential bugs or issues
- Security concerns
- Performance considerations
- Documentation and comments

### Step 3: Determine the recommendation

Based on the code review findings, choose the recommendation to state in the `**Recommendation**` line of the template below. It is advice for a human reviewer to ratify, not a GitHub review state:
- **APPROVE**: Code looks good, no significant issues found
- **REQUEST_CHANGES**: Critical issues that must be fixed before merging
- **COMMENT**: Suggestions or minor issues that don't block merging

### Step 4: Post the review

Post the review to GitHub as a comment (never `gh pr review`):
```
gh pr comment $ARGUMENTS --body "YOUR_REVIEW_BODY"
```

Format your review body using this template with collapsible sections:

```markdown
## PR Review

**Recommendation**: APPROVE | REQUEST_CHANGES | COMMENT

### Summary
[1-2 sentence overview of what this PR does]

<details>
<summary>Actionable Feedback (N items)</summary>

List specific items that need attention. Use checkboxes for trackable items:

- [ ] `file.py:42` - Description of issue or required change
- [ ] `notebook.ipynb` (in cell with `some_code = ...`) - Description
- [ ] General: Description of non-file-specific feedback

</details>

<details>
<summary>Detailed Review</summary>

### Code Quality
[Analysis of code patterns, readability, maintainability]

### Security
[Any security considerations or concerns]

### Suggestions
[Optional improvements that aren't blocking]

### Positive Notes
[What was done well - be specific]

</details>
```

**Guidelines:**
- Keep the summary and actionable feedback visible (outside collapsed sections)
- Put detailed analysis in the collapsed "Detailed Review" section to reduce noise
- Use checkboxes in actionable feedback so authors can track what they've addressed
- For Jupyter notebooks, reference code snippets instead of cell numbers (e.g., "in cell with `data = pd.read_csv(...)`")

**Important:** Only run the `gh pr comment` command once - it prints the comment URL on success; do not retry.
