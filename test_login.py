import json, hashlib

users = json.load(open('users.json','r',encoding='utf-8'))
email = 'emrahfirat444@gmail.com'
password = '123456'

user = None
for u in users.get('users',[]):
    if u.get('email','').lower() == email.lower():
        user = u
        break

if not user:
    print('User not found')
else:
    expected_hash = user.get('password_hash','')
    got = hashlib.sha256(password.encode()).hexdigest()
    print('expected:', expected_hash)
    print('computed:', got)
    print('match:', expected_hash == got)
