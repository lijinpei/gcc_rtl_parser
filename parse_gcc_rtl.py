from enum import Enum
import sys

class TokenKind(Enum):
    OpenParen = 1
    CloseParen = 2
    OpenBracket = 3
    CloseBracket = 4
    Identifier = 5
    Number = 6
    String = 7

class ASTKind(Enum):
    Identifier = 1
    Number = 2
    String = 3
    List = 4
    Vector = 5

def is_hex(c:str) -> bool:
    return c.isdigit() or (c >= 'a' and c <= 'f') or (c >= 'A' and c <= 'F')

def is_rtl_ident_char(c:str) -> bool:
    return c.isidentifier() or c == '<' or c == '>'

def skip_space(buffer:str, start:int):
    buffer_len = len(buffer)
    while start < buffer_len:
        if start + 2 <= buffer_len and buffer[start:start + 2] == ';;':
            start = skip_line(buffer, start + 2)
            continue
        if start < buffer_len and buffer[start].isspace():
            while start < buffer_len and buffer[start].isspace():
                start += 1
            continue
        break
    return start

def skip_line(buffer:str, start:int):
    while buffer[start] != '\n':
        start += 1
    return start + 1

def lex_OpenParen(buffer:str, start:int):
    return (start + 1, (TokenKind.OpenParen, None))

def lex_CloseParen(buffer:str, start:int):
    return (start + 1, (TokenKind.CloseParen, None))

def lex_OpenBracket(buffer:str, start:int):
    return (start + 1, (TokenKind.OpenBracket, None))

def lex_CloseBracket(buffer:str, start:int):
    return (start + 1, (TokenKind.CloseBracket, None))

def lex_Identifier(buffer:str, start:int):
    buffer_len = len(buffer)
    end = start
    # '<name>' is rtl's special syntax for iterator
    while end < buffer_len and is_rtl_ident_char(buffer[end]):
        end += 1
    return (end, (TokenKind.Identifier, buffer[start:end]))

def lex_Number(buffer:str, start:int):
    buffer_len = len(buffer)
    end = start
    while end < buffer_len and (buffer[end].isdigit()):
        end += 1
    return (end, tupel(TokenKind.Number, buffer[start:end]))

def lex_c_string(buffer:str, start:int):
    buffer_len = len(buffer)
    end = start + 1
    result = ""
    while end < buffer_len:
        c = buffer[end]
        if c == '"':
            return (end + 1, (TokenKind.String, result))
        if c == '\\':
            end = skip_code_c_style_escape(buffer, end)
            if end >= buffer_len:
                raise ValueError()
        result = result + buffer[end]
        end += 1

def skip_code_c_style_escape(buffer:str, start:int):
    c = buffer[start + 1]
    if c == 'x':
        start += 2
        while is_hex(buffer[start]):
            start += 1
        return start
    if c == 'u':
        start += 4
    elif c == 'U':
        start += 8
    elif c.isdigit():
        start += 3
    return start + 2

def skip_code_c_string(buffer:str, start:int):
    while True:
        c = buffer[start]
        if c == '"':
            return start + 1
        if c == '\\':
            start = skip_code_c_style_escape(buffer, start)
        else:
            start += 1

def skip_code_c_char(buffer:str, start:int):
    # this is mostly like skip_code_c_string, no much sanity check
    while True:
        c = buffer[start]
        if c == "'":
            return start + 1
        if c == '\\':
            start = skip_code_c_style_escape(buffer, start)
        else:
            start += 1

def skip_code_block_comment(buffer:str, start:int):
    while buffer[start:start+1] != '*/':
        start = start + 1
    return start + 2

def skip_code_line_comment(buffer:str, start:int):
    return skip_line(buffer, start)

def lex_code_string(buffer:str, start:int):
    buffer_len = len(buffer)
    brace_depth = 1
    end = start + 1
    # no sanity check or buffer overflow check in this block of code
    while brace_depth != 0:
        c = buffer[end]
        if c == '/' and buffer[end + 1] == '*':
            end = skip_code_block_comment(buffer, end)
            continue
        elif c == '/' and buffer[end + 1] == '/':
            end = skip_code_line_comment(buffer, end)
            continue
        elif c == '"':
            end = skip_code_c_string(buffer, end)
            continue
        elif c == "'":
            end = skip_code_c_char(buffer, end)
            continue
        if c == '{':
            brace_depth += 1
        elif c == '}':
            brace_depth -= 1
        end += 1
    return (end, (TokenKind.String, buffer[start:end]))

def get_lex_handler(buffer:str, start:int):
    c = buffer[start]
    if c.isdigit():
        return lex_Number
    if is_rtl_ident_char(c):
        return lex_Identifier
    switcher = {
        '(': lex_OpenParen,
        ')': lex_CloseParen,
        '[': lex_OpenBracket,
        ']': lex_CloseBracket,
        '{': lex_code_string,
        '"': lex_c_string,
    }
    handler = switcher.get(c, None)
    return handler

class Lexer:
    def __init__(self, file_name:str):
        self.buffer = []
        self.next = 0
        with open(file_name, 'r') as fin:
            buffer = fin.read()
            start = 0
            buffer_len = len(buffer)
            while start < buffer_len:
                start = skip_space(buffer, start)
                if (start >= buffer_len):
                    return
                handler = get_lex_handler(buffer, start)
                start, token = handler(buffer, start)
                self.buffer.append(token)

    def peek(self, arg = None):
        if arg == None:
            arg = 0
        if isinstance(arg, int):
            return self.buffer[self.next + arg]
        elif isinstance(arg, TokenKind):
            return self.buffer[self.next][0] == arg
        else:
            raise ValueError()
    def consume(self, arg):
        if arg != None:
            assert self.buffer[self.next][0] == arg
        result = self.buffer[self.next]
        self.next += 1
        return result


# token is tuple(TokenKind, data)
# ASTNode is tuple(ASTKind, data)
def parse_rtl_identifier(lexer: Lexer):
    return (ASTKind.Identifier, lexer.consume(TokenKind.Identifier)[1])

def parse_rtl_number(lexer: Lexer):
    return (ASTKind.Number, lexer.consume(TokenKind.Number)[1])

def parse_rtl_string(lexer: Lexer):
    return (ASTKind.String, lexer.consume(TokenKind.String)[1])

def parse_rtl_list(lexer: Lexer):
    result = []
    lexer.consume(TokenKind.OpenParen)
    while not lexer.peek(TokenKind.CloseParen):
        result.append(parse_rtl_primary(lexer))
    lexer.consume(TokenKind.CloseParen)
    return (ASTKind.List, result)

def parse_rtl_vector(lexer: Lexer):
    result = []
    lexer.consume(TokenKind.OpenBracket)
    while not lexer.peek(TokenKind.CloseBracket):
        result.append(parse_rtl_primary(lexer))
    lexer.consume(TokenKind.CloseBracket)
    return (ASTKind.Vector, result)

def parse_rtl_primary(lexer: Lexer):
    token = lexer.peek()
    switcher = {
        TokenKind.OpenParen: parse_rtl_list,
        TokenKind.OpenBracket: parse_rtl_vector,
        TokenKind.Identifier: parse_rtl_identifier,
        TokenKind.Number: parse_rtl_number,
        TokenKind.String: parse_rtl_string,
    }
    def error_handler(lexer: Lexer):
        raise ValueError()

    handler = switcher.get(lexer.peek()[0], error_handler)
    return handler(lexer)

def dump_indent(indent:int, os) -> int:
    print(' ' * indent, file=os, end='')
    return indent + 4

def dump_ast_identifier(ast, indent, os):
    dump_indent(indent, os)
    print('idt: {}'.format(ast[1]), file=os, end='')

def dump_ast_number(ast, indent, os):
    dump_indent(indent, os)
    print('num: {}'.format(ast[1]), file=os, end='')

def dump_ast_string(ast, indent, os):
    dump_indent(indent, os)
    print('str: "{}"'.format(ast[1]), file=os, end='')

def dump_ast_list(ast, indent, os):
    indent = dump_indent(indent, os)
    print('list:', file=os)
    for member in ast[1]:
        dump_ast(member, indent, os)
        print(file=os)

def dump_ast_vector(ast, indent, os):
    indent = dump_indent(indent, os)
    print('vector:', file=os)
    for member in ast[1]:
        dump_ast(member, indent, os)
        print(file=os)

def dump_ast(ast, indent = 0, os = sys.stdout):
    switcher = {
        ASTKind.Identifier: dump_ast_identifier,
        ASTKind.Number: dump_ast_number,
        ASTKind.String: dump_ast_string,
        ASTKind.List: dump_ast_list,
        ASTKind.Vector: dump_ast_vector,
    }
    switcher[ast[0]](ast, indent, os)

if __name__ == '__main__':
    lexer = Lexer(sys.argv[1])
    while lexer.next < len(lexer.buffer):
        dump_ast(parse_rtl_list(lexer))
