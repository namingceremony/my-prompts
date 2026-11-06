What does this print?
def add(item, bucket=[]):
    bucket.append(item)
    return bucket
add(1)
print(add(2))
A. [2]
B. [1, 2]
C. TypeError
D. [[1], [2]]
Correct: B — The default list is created once, when the function is defined, and shared across calls.
Use bucket=None and create the list inside.
Probe: Why might this bug appear only in production and not in a unit test?
Score: ____ / 5 Notes: ______________________________________________
PY-02
CORE · Intermediate · ~0.75 min
What is the value of a after this code runs?
a = [[1, 2], [3, 4]]
b = a.copy()
b[0].append(9)
b.append([5])
A. [[1, 2], [3, 4]]
B. [[1, 2, 9], [3, 4]]
C. [[1, 2, 9], [3, 4], [5]]
D. [[1, 2], [3, 4], [5]]
Correct: B — copy() is shallow: a new outer list, but the inner lists are shared. Mutating b[0] affects
a; appending to b does not. copy.deepcopy() copies the inner lists too.
Probe: When would deepcopy be a bad idea?
Score: ____ / 5 Notes: ______________________________________________
Page 14
Interview kit · Sahithi Rachamalla · Junior AI/ML Engineer · Confidential
PY-03
CORE · Intermediate · ~0.75 min
What does this print?
g = (x * x for x in range(3))
print(sum(g), sum(g))
A. 5 5
B. 5 0
C. 0 5
D. TypeError
Correct: B — A generator can be iterated only once. The first sum consumes it (0 + 1 + 4 = 5); the
second finds it exhausted.
Probe: Why would you use a generator rather than a list when embedding a million documents?
Score: ____ / 5 Notes: ______________________________________________
PY-04
CORE · Intermediate · ~0.75 min
Which of these can be used as a dictionary key?
A. [1, 2]
B. {1, 2}
C. (1, [2])
D. (1, (2, 3))
Correct: D — Keys must be hashable. Lists and sets are mutable and unhashable. A tuple is
hashable only if every element is hashable, so (1, [2]) fails when used as a key.
Probe: Why does Python require keys to be immutable?
Score: ____ / 5 Notes: ______________________________________________
PY-05
OPTIONAL · Intermediate · ~0.75 min
What does f() return?
def f():
    try:
        return "try"
    finally:
        return "finally"
A. "try"
B. "finally"
C. None
D. SyntaxError
Correct: B — finally always runs, and a return inside it overrides the earlier one — it also silently
swallows exceptions. Recent Python versions warn about return in finally for this reason.
Probe: What is the legitimate use of finally?
Score: ____ / 5 Notes: ______________________________________________
Page 15
Interview kit · Sahithi Rachamalla · Junior AI/ML Engineer · Confidential
PY-06
OPTIONAL · Intermediate · ~0.75 min
What does this print?
fs = [lambda: i for i in range(3)]
print([f() for f in fs])
A. [0, 1, 2]
B. [2, 2, 2]
C. [0, 0, 0]
D. NameError
Correct: B — Closures look up i when called, not when created (late binding). By then i is 2. Fix with
lambda i=i: i.
Probe: How does this show up when building callbacks in a loop?
Score: ____ / 5 Notes: ______________________________________________
PY-07
OPTIONAL · Intermediate · ~0.75 min
What does this print?
class A:
    items = []
a, b = A(), A()
a.items.append(1)
print(b.items)
A. []
B. [1]
C. AttributeError
D. None
Correct: B — items is a class attribute shared by all instances. Mutable per-instance state belongs in
__init__.
Probe: What would change if the line were a.items = [1] instead?
Score: ____ / 5 Notes: _____________________________________________
