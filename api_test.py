import requests

import openai


with open('api_key.key') as f:
    API_KEY = f.read()


def main():
    openai.api_key = API_KEY
    response = openai.ChatCompletion.create(
        model='gpt-3.5-turbo',
        messages=[
            {
                'role': 'user',
                'content': 'Multiply every equation by 2. What is the result of equation: 1*30'
            }
        ]
    )
    print(response)
    

if __name__ == '__main__':
    main()
