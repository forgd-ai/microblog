# Welcome to Microblog!

This is an example application featured in my [Flask Mega-Tutorial](https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world). See the tutorial for instructions on how to work with it.

The version of the application featured in this repository corresponds to the 2024 edition of the Flask Mega-Tutorial. You can find the 2018 and 2021 versions of the code [here](https://github.com/miguelgrinberg/microblog-2018). And if for any strange reason you are interested in the original code, dating back to 2012, that is [here](https://github.com/miguelgrinberg/microblog-2012).

## Using the API

Get a token with your username and password, then send it as a bearer token:

```
http --auth <username>:<password> POST http://localhost:5001/api/tokens
http GET http://localhost:5001/api/users/1 "Authorization:Bearer <token>"
```

Tokens last one hour. Call `POST /api/tokens` again to get a fresh one.
