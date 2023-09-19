import openai
from openai.error import InvalidRequestError


with open('api_key.key') as f:
    API_KEY = f.read()


def main():
    openai.api_key = API_KEY
    try:
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo',
            messages=[
                {
                    'role': 'user',
                    'content': 'How are you?'
                }
            ],
            max_tokens=None,
            temperature=None,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=2
        )
    except InvalidRequestError as exc:
        print(str(exc))
    choices = response['choices']
    for choice in choices:
        message = choice['message']
        print('Role', message['role'])
        print(message['content'])


if __name__ == '__main__':
    main()


# ChatGPT's parameters can be configured to control various aspects of the model's interaction. Some of the key parameters include:

# 1. `max_tokens`: This parameter allows you to determine the maximum length of the model’s output in tokens.

# 2. `temperature`: Controls the randomness of the model’s response. A higher value (close to 1) makes the output more random, while a lower value (close to 0) encourages more determinism.

# 3. `top_p`: Used for nucleus sampling, sets the cumulative probability threshold. The model keeps generating tokens and stops when the cumulative probability exceeds the provided top_p.

# 4. `frequency_penalty`: A hyper-parameter that penalizes common words and phrases, potentially encouraging diversity and novelty in the output.

# 5. `presence_penalty`: Determines how the model behaves towards "inventing" new details. A higher penalty makes the model less likely to generate information that wasn't explicitly in the prompt.

# 6. `return_prompt`: Return the conversation so far along with model output if set to `True`.

# 7. `role`: This can be set to 'system', 'user', 'assistant' depending on the role of a particular message in the conversation.

# 8. `messages`: The history of the conversation, composed of an array of message objects. This parameter is crucial in the formation of ChatGPT's responses.

# 9. `use_cache`: Determines if a prior model token generation can be used for future predictions. 

# 10. `echo`: When it is set to 'True', it reuses previous user messages.

# 11. `stop_sequences`: A list of strings. The model will stop generating further tokens once any of the stop sequences are generated.

# It's important to note not all parameters are offered through all platforms and APIs offering GPT-3 services, so always refer to the specifics of a given platform's documentation.
