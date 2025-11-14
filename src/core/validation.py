# import pydantic
import pydantic


class DataModel(pydantic.BaseModel):
    pass


rules = { # past pydantic just for a more semantic
    "name": lambda x: x.count(" ") >= 1,
}



def validate_data(x: dict) -> pydantic.BaseModel:

    pass
