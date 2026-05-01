```markdown
# agent-skill-infra Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches you the core development patterns and conventions found in the `agent-skill-infra` Python codebase. You'll learn about file naming, import/export styles, commit message conventions, and the basic workflows for contributing to and maintaining the repository. The guide also covers the project's testing patterns and provides handy commands for common tasks.

## Coding Conventions

### File Naming
- Use **snake_case** for all Python files.
  - Example: `my_module.py`, `data_loader.py`

### Import Style
- Use **relative imports** within the package.
  - Example:
    ```python
    from .utils import helper_function
    ```

### Export Style
- Use **named exports** (explicitly define what is exported).
  - Example:
    ```python
    __all__ = ['MyClass', 'my_function']
    ```

### Commit Messages
- Follow **Conventional Commits**.
- Common prefixes: `chore`, `style`
- Keep commit messages concise (about 50 characters).
  - Example:
    ```
    chore: update dependencies
    style: fix linting issues in utils.py
    ```

## Workflows

### Code Formatting and Style
**Trigger:** Before committing code or opening a pull request  
**Command:** `/format-style`

1. Ensure all file names use snake_case.
2. Check imports use relative paths where possible.
3. Run a linter (e.g., `flake8` or `pylint`) to enforce style.
4. Stage and commit with a conventional message.

### Dependency Maintenance
**Trigger:** When updating or adding dependencies  
**Command:** `/update-deps`

1. Update the relevant dependency files (e.g., `requirements.txt`).
2. Run tests to ensure compatibility.
3. Commit with a `chore:` prefix.
4. Push changes and open a pull request if needed.

### Writing Commits
**Trigger:** When making any code change  
**Command:** `/commit`

1. Stage your changes.
2. Write a commit message using the conventional format:
   - Prefix (`chore`, `style`), colon, brief description.
   - Example: `chore: add logging to agent startup`
3. Commit and push.

## Testing Patterns

- Test files are written in TypeScript with the pattern `*.test.ts`.
- The specific testing framework is unknown, but tests are likely located in files ending with `.test.ts`.
- To write a new test, create a file like `my_feature.test.ts`.
- Ensure tests cover the relevant Python functionality, possibly via integration or API bindings.

## Commands
| Command         | Purpose                                         |
|-----------------|-------------------------------------------------|
| /format-style   | Format code and check for style consistency     |
| /update-deps    | Update dependencies and verify compatibility    |
| /commit         | Make a conventional commit                      |
```
