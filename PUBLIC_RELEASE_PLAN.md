# Public Release Plan

Plan for making the whatsapp-mcp repository ready for public release.

## Critical Issues (Must Fix)

### 1. Remove hard-coded paths from plist file
**File:** `whatsapp-bridge/com.whatsapp.bridge.plist`

The file contains hard-coded paths exposing username and directory structure:
```
/Users/amer/Code/whatsapp-mcp/...
```

**Fix:**
- Rename to `com.whatsapp.bridge.plist.example`
- Replace hard-coded paths with placeholders (e.g., `{{WORKDIR}}` or comments)
- Update `setup-daemon.sh` to generate the actual plist with user-specific paths
- Add the actual plist to `.gitignore`

### 2. Remove debug print statements
**File:** `whatsapp-bridge/main.go`

Remove or make conditional:
- Line ~292: `fmt.Println("Media uploaded", resp)`
- Line ~935: `fmt.Println("Received request to send message", ...)`
- Line ~939: `fmt.Println("Message sent", ...)`

## Recommended Additions

### 3. Add SECURITY.md
Create a security policy explaining:
- Privacy implications of the tool
- Where data is stored (locally only)
- Recommendations for secure setup
- Reference the "lethal trifecta" warning from README

### 4. Add CONTRIBUTING.md
Standard open-source contribution guidelines.

### 5. Add CHANGELOG.md (Optional)
Version tracking for releases.

## Already Good

- [x] No hardcoded secrets, API keys, or credentials
- [x] `.gitignore` properly excludes databases, logs, local configs
- [x] README well-documented with setup instructions
- [x] MIT License included
- [x] Code quality solid with proper error handling
- [x] Data stays local - good security design
