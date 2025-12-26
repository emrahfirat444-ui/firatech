import json, hashlib, uuid

identifier = 'emrahfirat444@gmail.com'
password = '123456'

users = json.load(open('users.json','r',encoding='utf-8'))
user = None
for u in users.get('users',[]):
    if u.get('email','').lower() == identifier.lower() or u.get('id') == identifier or (isinstance(u.get('name'), str) and u.get('name').lower() == identifier.lower()):
        user = u
        break

if not user:
    print('RESULT: failed')
    print('reason: user not found')
else:
    if not user.get('is_active', False):
        print('RESULT: failed')
        print('reason: user inactive')
    else:
        expected = user.get('password_hash','')
        got = hashlib.sha256(password.encode()).hexdigest()
        if expected != got:
            print('RESULT: failed')
            print('reason: wrong password')
        else:
            token = f"token_{uuid.uuid4().hex[:16]}"
            print('RESULT: success')
            print('token:', token)
            print('user:')
            print('  id:', user.get('id'))
            print('  email:', user.get('email'))
            print('  name:', user.get('name'))
            print('  role:', user.get('role'))
