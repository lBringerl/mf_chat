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
                'content': 'Привет'
            }
        ]
    )
    choices = response['choices']
    for choice in choices:
        message = choice['message']
        print('Role', message['role'])
        print(message['content'])


if __name__ == '__main__':
    main()
