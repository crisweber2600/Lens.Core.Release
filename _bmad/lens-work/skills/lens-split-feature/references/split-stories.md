# Move Stories

Use `move-stories` after the split feature shell exists.

1. Resolve each requested story file in the source feature.
2. Read and normalize each story status.
3. Stop if any selected story is still `in-progress`.
4. Move the remaining story files into the target feature `stories/` folder.