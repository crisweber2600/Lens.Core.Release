# Validate Split

Use `validate-split` before any split execution.

1. Read the sprint plan or status source.
2. Normalize each selected story status.
3. Block the split if any selected story resolves to `in-progress`.
4. Proceed to `create-split-feature` only after validation passes.