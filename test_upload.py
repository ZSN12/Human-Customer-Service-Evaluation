import requests

url = 'http://localhost:8001/api/upload'
files = {'file': open('test.csv', 'rb')}

response = requests.post(url, files=files)
print('Status code:', response.status_code)
print('Response:', response.text)
