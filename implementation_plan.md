# Implementation Plan - Fix GOAP Goal Reachability Issue

## Task: Fix GOAP Goal Reachability Contradiction

### Goal
Resolve the contradiction where GOAP planning reports "Goal appears to be unreachable from current state" despite having:
- 100% action executability (118/118 actions)
- Planning successful: True
- Creates plans with cost 1 in fast time (~0.1s)

### Root Cause Analysis
The issue likely stems from one of these areas:
1. **Goal State Definition**: The "gain xp" goal may be improperly defined or mapped
2. **Initial State vs Target State**: Mismatch between current character state and goal requirements
3. **GOAP Planner Logic**: Bug in reachability analysis vs plan creation logic
4. **Action-Goal Mapping**: Actions may not properly declare their effects for XP gain

### Investigation Approach
1. **Examine Goal Definition**: Check how "gain xp" goal is translated to GOAP target state
2. **Review Action Effects**: Verify combat/gathering actions declare XP gain effects
3. **Debug GOAP Logic**: Trace why reachability analysis fails while planning succeeds
4. **Test with Simple Goals**: Validate with basic movement goals first

### Files to Investigate
- `src/ai_player/diagnostics/planning_diagnostics.py` - Where reachability is analyzed
- `src/cli/commands/diagnostics.py` - Where goal parsing occurs
- `src/ai_player/actions/combat_action.py` - XP effects declaration
- `src/ai_player/actions/gathering_action.py` - XP effects declaration
- `src/lib/goap.py` - GOAP planner reachability logic

### Implementation Strategy
1. **Add Debug Logging**: Trace goal state creation and reachability analysis
2. **Fix Goal State Mapping**: Ensure "gain xp" maps to achievable GOAP target state
3. **Verify Action Effects**: Ensure XP-gaining actions properly declare effects
4. **Test Incremental**: Start with simple goals, progress to XP goals

### Testing Strategy
- Test with movement goals first (should work perfectly)
- Test with "gain xp" goal and verify both planning success AND reachability
- Validate actual autonomous XP progression capability
- Confirm contradiction is resolved

### Success Criteria
- ✅ GOAP planning reports goal as reachable when actions are executable
- ✅ No contradiction between planning success and reachability analysis
- ✅ AI can execute XP-gaining sequences autonomously

### Estimated Effort
**30-60 minutes** - This appears to be a logical inconsistency that should have a targeted fix

### Risk Assessment
**Low Risk** - The core action system is working perfectly (100% executability), this is likely a reporting/logic issue in the diagnostics or goal mapping layer.

### Alternative Approaches
1. **Quick Fix**: Adjust reachability reporting to match planning success
2. **Root Fix**: Debug and fix the actual reachability analysis logic
3. **Bypass**: Focus on actual autonomous execution and ignore diagnostic contradiction

**Recommendation**: Start with Root Fix approach since it provides the most confidence in the system's correctness.