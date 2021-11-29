# Project MIX: API Documentation

*This documentation was created by Jackson Kennel, with additions from Kevin Chen's design.*

## Adding a Microservice:

In order to add a microservice to MIX, the microservice in question must make a `POST` request to the /microservice endpoint. The `POST` request must send JSON adhering to the following schema:

```
{
    'port' : 'HOST PORT',
    'ip' : 'HOST IP',
    'dependencies' : [
        {
            'port' : 'HOST PORT',
            'ip' : 'HOST IP',
            'dependencies' : [
                {
                    ...and so on. Dependencies can be infinitely nested.
                }
            ]
        },
        {
            'port' : 'HOST,
            'ip' : 'HOST IP',
            'dependencies' : []
        }
    ]
}
```

To track the IP of the microservice, MIX will fetch the IP from the request. MIX will run on `localhost:5000`.

To handle multiple IMs, MIX maintains a running list of all connected IMs. MIX will add all dependencies as if they were independent IMs. For dependency handling, see below.

## Removing a Microservice:

To remove a microservice from MIX, the microservice must make a `DELETE` request to the /microservice endpoint. The `DELETE` request must send JSON adhering to the following schema:

```
{ 
    'port' : 'HOST PORT'
    'ip' : 'HOST IP'
}
```

## Dependency Handling:

MIX will handle dependencies in a tree-like bottom-up fashion, retrieving the output of all of any IMs dependencies before making a request to that IM. IMs are not required to do dependency handling, as MIX will handle it. All IMs which have dependencies are assumed to not require location data. In order to avoid redundant requests to IMs, MIX maintains a running list of all IMs which have already had requests sent to them.

## Requirements for IMs:

- All IMs must have a '/' endpoint that can handle `GET` requests.
- All IMs must be on localhost to create a valid connection.
- All IMs must use `requests` to make HTTP requests.
- All IMs must return some JSON schema:
    - IMs which have dependencies are expected to be able to handle the JSON output of any of their dependencies.
    - IMs which do not have any dependency structure are expected to be able to handle the JSON sent by MIX to '/' described in the above section.

## Information Representation in MIX:

MIX will send the following JSON schema to all IMs which do not have any dependencies:

```
{
    'latitude' : float,
    'longitude' : float
}
```

For IMs with multiple dependencies, MIX will combine the JSON schema of each dependency to send to that IM. Consider the following example:

IM 1 has dependencies 2 and 3.

IM 2 has the following schema:

```
{
    'distance' : float
}
```

IM 3 has the following schema:

```
{
    'squared_distance' : float
}
```

IM 1 will receive the following schema as input:

```
{
    'distance' : float
    'squared_distance' : float
}
```

## Caching:

MIX will cache all responses from IMs. IMs must define the expiry age of their data in their responses, formatted as follows:

```
Content-Type: max-age=x
```

where x is some arbitrary number.