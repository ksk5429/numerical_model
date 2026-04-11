# Pre-Flight Checklist

Copy this template before every implementation task. Fill it out, show it to the AI or review it yourself before coding begins.

---

## Task: _______________________________________________

### Inputs
- [ ] Data files needed: _______________
- [ ] All data files exist on disk? Run `ls <path>` to verify
- [ ] External software needed (OptumGX, OpenFAST)? Is it running?

### Assumptions
- [ ] What physics am I assuming? _______________
- [ ] What unit convention? (Pa vs kPa, N vs kN) _______________
- [ ] What L/D range is this valid for? _______________
- [ ] What soil type? (clay/sand/layered) _______________

### Scope
- [ ] What's the expected output? (figure, JSON, CSV, code module)
- [ ] How will I verify correctness? (published reference, analytical check, self-consistency)
- [ ] Estimated time: _______________

### Human Approval
- [ ] Does this change a physics formula? → STOP, verify against paper first
- [ ] Does this add a new dependency? → Check PyPI availability
- [ ] Does this modify a validated benchmark? → Will it still pass?

### Go / No-Go
- [ ] All inputs available
- [ ] Assumptions documented
- [ ] Verification plan exists
- **Decision:** [ ] GO [ ] STOP — missing: _______________
