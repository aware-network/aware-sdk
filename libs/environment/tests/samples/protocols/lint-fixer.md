# Lint Fixer Protocol

AI-guided code quality improvement with live error detection.

## Step 1: Read Code

<!-- command:exec -->
```
code read --path sample.py
```

Analyze the code structure above.

## Step 2: Check Errors

<!-- command:exec -->
```
code lint --path sample.py
```

Review lint errors. Common issues: unused imports, formatting, type annotations.

## Step 3: Fix Issues

Based on the actual errors shown above, apply fixes.

<!-- command:required -->
```
code write --path sample.py --content <fixed-code>
```

Replace `<fixed-code>` with corrected implementation addressing all lint errors.

## Step 4: Verify Fix

<!-- command:suggested -->
```
code lint --path sample.py
```

Re-run linter to confirm all issues resolved. If errors remain, return to Step 3.

## Step 5: Format Code

<!-- command:suggested -->
```
code format --path sample.py
```

Optional: Apply standard formatting for consistency.
