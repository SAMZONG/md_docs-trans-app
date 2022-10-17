from typing import Any, ClassVar, Dict, List, Optional

import pydantic


class BaseBlock(pydantic.BaseModel):
    IS_TRANSLATABLE: ClassVar[bool] = False

    @pydantic.root_validator(pre=True)
    def validate(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(values, dict):
            children = values.get('children')
            if children:
                parsed_children = []
                for child in children:
                    if isinstance(child, dict) and 'block_type' in child:
                        block_type = child.pop('block_type')
                        if block_type not in globals():
                            raise ValueError('Unknown Block Type: %s', block_type)
                        block = globals()[block_type](**child)
                    else:
                        block = child
                    parsed_children.append(block)
                values['children'] = parsed_children
        return values

    def dict(self, *args, **kwargs) -> dict:
        data = super().dict(*args, **kwargs)
        data['block_type'] = self.__class__.__name__
        return data

    def should_be_translated(self) -> bool:
        return False

    def __str__(self) -> str:
        raise NotImplementedError()


class Translatable(pydantic.BaseModel):
    text: str
    translated_text: Optional[str] = None

    def __str__(self) -> str:
        if self.translated_text is None:
            '\n\n'.join([self.text, self.translated_text])
        return self.text

    def should_be_translated(self) -> bool:
        return self.translated_text is None

    def get_data_to_translate(self):
        raise NotImplementedError()


class RawDataBlock(BaseBlock):
    name: str
    data: Any

    def __str__(self) -> str:
        return str(self.data)

    def __bool__(self):
        return bool(self.data)


class TextBlock(Translatable, BaseBlock):
    IS_TRANSLATABLE = True

    strong: bool = False
    emphasis: bool = False

    @pydantic.validator('text', pre=True)
    def validate_text(cls, value):
        if isinstance(value, list):
            return ''.join(map(str, value))
        return value

    def __str__(self) -> str:
        if self.strong:
            return f'**{self.text}**'
        if self.emphasis:
            return f'*{self.text}*'
        return self.text

    def get_data_to_translate(self):
        return self.text


class LinkBlock(BaseBlock):
    IS_TRANSLATABLE = True

    link: str
    title: Optional[str] = None
    text: Optional[List[BaseBlock]] = None

    def __str__(self) -> str:
        return f'[{str(" ".join(map(str, self.text)) or self.title)}]({self.link})'


class ImageBlock(BaseBlock):
    IS_TRANSLATABLE = True

    src: str
    alt: str = pydantic.Field(default=str)
    title: Optional[str] = None

    def __str__(self) -> str:
        return f'![{self.alt}]({self.src})'


class HeadingBlock(Translatable, BaseBlock):
    level: int
    text: str

    def __str__(self) -> str:
        return f'{"#" * self.level} {str(self.text)}'

    def data_to_translate(self) -> Optional[str]:
        return self.text


class SeparatorBlock(BaseBlock):
    def __str__(self) -> str:
        return '---'


class CodeBlock(BaseBlock):
    code: str
    language: Optional[str] = None

    def __str__(self) -> str:
        lang = self.language or ''
        return f'```{lang}\n{self.code}\n```'


class HtmlBlock(BaseBlock):
    code: str

    def __str__(self) -> str:
        return self.code


class ListItemBlock(BaseBlock):
    children: List[Translatable]

    def __str__(self) -> str:
        return ''.join([str(child) for child in self.children])


class ListBlock(BaseBlock):
    children: List['ListItemBlock']
    ordered: bool = False

    def __str__(self) -> str:
        return '\n'.join(
            [
                f'{f"{counter}." if self.ordered else "*"} {str(item)}'
                for counter, item in enumerate(self.children)
            ]
        )
