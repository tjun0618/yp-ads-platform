s = '\\n\\n'
print(repr(s))
print('---')
print('in JS this would be:', s)
print('---')
# What we actually want in JS: split by two newlines
s2 = '\n\n'
print('correct JS: split by', repr(s2))
