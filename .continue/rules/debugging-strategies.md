---
name: debugging-strategies
description: debugging-strategies skill migrated from Windsurf as contextual rules
alwaysApply: false
---

# Debugging Strategies

Transform debugging from frustrating guesswork into systematic problem-solving with proven strategies, powerful tools, and methodical approaches.

## When to Use This Skill

- Tracking down elusive bugs
- Investigating performance issues
- Understanding unfamiliar codebases
- Debugging production issues
- Analyzing crash dumps and stack traces
- Profiling application performance
- Investigating memory leaks
- Debugging distributed systems

## Core Principles

### 1. The Scientific Method

**1. Observe**: What's the actual behavior?
**2. Hypothesize**: What could be causing it?
**3. Experiment**: Test your hypothesis
**4. Analyze**: Did it prove/disprove your theory?
**5. Repeat**: Until you find the root cause

### 2. Debugging Mindset

**Don't Assume:**
- "It can't be X" - Yes it can
- "I didn't change Y" - Check anyway
- "It works on my machine" - Find out why

**Do:**
- Reproduce consistently
- Isolate the problem
- Document everything
- Use systematic approaches

## Systematic Debugging Process

### Phase 1: Reproduction & Isolation

1. **Reproduce the Issue**
   - Get exact steps to reproduce
   - Note environment conditions
   - Capture error messages precisely
   - Document timing/frequency

2. **Isolate the Problem Area**
   - Binary search: comment out sections
   - Create minimal reproduction case
   - Test in isolation
   - Verify dependencies

3. **Gather Context**
   - Recent changes in the area
   - Similar issues in the past
   - System state at time of error
   - Related configuration changes

### Phase 2: Hypothesis Generation

4. **Form Multiple Hypotheses**
   - Brainstorm all possible causes
   - Rate by probability
   - Consider edge cases
   - Don't dismiss "impossible" causes

5. **Prioritize Investigation**
   - Start with most likely
   - Consider easiest to test first
   - Factor in impact/criticality
   - Plan test sequence

### Phase 3: Systematic Testing

6. **Design Controlled Experiments**
   - Change one variable at a time
   - Document expected vs actual
   - Use proper logging/monitoring
   - Create test cases

7. **Use Appropriate Tools**
   - **Python**: pdb, ipdb, logging, trace
   - **JavaScript**: debugger, console.log, breakpoints
   - **Performance**: profilers, flame graphs
   - **Memory**: valgrind, heap analyzers
   - **Network**: Wireshark, tcpdump

### Phase 4: Analysis & Resolution

8. **Analyze Results**
   - Compare expected vs actual
   - Look for patterns
   - Consider secondary effects
   - Validate root cause

9. **Implement Fix**
   - Make minimal, targeted changes
   - Add regression tests
   - Document the fix
   - Verify no side effects

## Technology-Specific Strategies

### Python Debugging

**Essential Tools:**
```python
import pdb; pdb.set_trace()  # Breakpoint
import logging; logging.basicConfig(level=logging.DEBUG)
import traceback; traceback.print_exc()
```

**Common Patterns:**
- Use `assert` statements for invariants
- Leverage `__repr__` for object inspection
- Use `dir()` and `help()` for exploration
- Check `sys.path` for import issues

### JavaScript/Node.js Debugging

**Essential Tools:**
```javascript
console.log('Debug point:', variable);
debugger; // Browser breakpoint
process.exit(1); // Node.js early exit
```

**Common Patterns:**
- Use browser dev tools extensively
- Check network tab for API issues
- Use `typeof` and `instanceof` for type checking
- Leverage async/await stack traces

### System/Infrastructure Debugging

**Essential Commands:**
```bash
# Process monitoring
ps aux | grep process_name
top -p PID
strace -p PID

# Network debugging
netstat -tulpn
tcpdump -i eth0
curl -v URL

# File system
lsof +D /directory
find /path -name "*.log"
tail -f /var/log/app.log
```

## Advanced Techniques

### 1. Differential Debugging
- Compare working vs broken versions
- Use `git bisect` for regression hunting
- A/B test different approaches
- Environment swapping

### 2. Stress Testing
- Reproduce under load
- Test edge cases systematically
- Use fuzzing for input validation
- Monitor resource exhaustion

### 3. Remote Debugging
- Set up remote debuggers
- Use log aggregation
- Implement health checks
- Monitor production metrics

## Common Pitfalls & Solutions

| Pitfall | Solution |
|---|---|
| Fixing symptoms instead of root cause | Keep asking "why" 5 times |
| Making multiple changes at once | Change one thing at a time |
| Ignoring error messages | Read and understand every error |
| Assuming recent changes are the cause | Check entire system state |
| Not documenting findings | Keep a debugging journal |

## Quick Reference Checklist

**Initial Investigation:**
- [ ] Reproduce consistently
- [ ] Capture exact error messages
- [ ] Note environment conditions
- [ ] Check recent changes
- [ ] Verify dependencies

**Systematic Approach:**
- [ ] Form multiple hypotheses
- [ ] Prioritize by probability
- [ ] Design controlled experiments
- [ ] Use appropriate tools
- [ ] Document everything

**Resolution:**
- [ ] Identify root cause
- [ ] Implement minimal fix
- [ ] Add regression tests
- [ ] Document solution
- [ ] Verify no side effects

Use this prompt by typing `/debugging-strategies` when you need systematic debugging guidance.
