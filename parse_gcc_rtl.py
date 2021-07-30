from enum import Enum
import sys
import os

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
    Bad = 6

def is_hex(c:str) -> bool:
    return c.isdigit() or (c >= 'a' and c <= 'f') or (c >= 'A' and c <= 'F')

def is_rtl_ident_char(c:str) -> bool:
    return c.isdigit() or c.isidentifier() or c in '<>:*?'

def skip_space(buffer:str, start:int):
    buffer_len = len(buffer)
    while start < buffer_len:
        if start + 2 <= buffer_len:
            if buffer[start:start + 2] == '/\n':
                start += 2
                continue
            if buffer[start:start + 2] == '/*':
                start = skip_code_block_comment(buffer, start)
                continue
        if buffer[start] == ';':
            start = skip_line(buffer, start + 1)
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

def lex_HexNumber(buffer:str, start:int):
    buffer_len = len(buffer)
    end = start + 2
    while end < buffer_len and is_hex(buffer[end]):
        end += 1
    return (end, (TokenKind.Number, buffer[start:end]))

def lex_Number(buffer:str, start:int):
    buffer_len = len(buffer)
    end = start
    if start + 2 <= buffer_len and buffer[start:start + 2] == '0x':
        return lex_HexNumber(buffer, start)
    while end < buffer_len and (buffer[end].isdigit()):
        end += 1
    return (end, (TokenKind.Number, buffer[start:end]))

def lex_negative_number(buffer:str, start:int):
    end, (_, s) = lex_Number(buffer, start + 1)
    return (end, (TokenKind.Number, '-' + s))

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
            continue
        result = result + buffer[end]
        end += 1
    return (end, (TokenKind.String, result))

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
    while buffer[start:start+2] != '*/':
        start += 1
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
    # 64x2mode is a identifier for rtl
    end = start + 1
    buffer_len = len(buffer)
    while end < buffer_len:
        if not is_rtl_ident_char(buffer[end]):
            break
        end += 1
    def valid_hex_number(buffer, start, end):
        if end - start <= 2:
            return False
        if buffer[start:start + 2] != '0x':
            return False
        for c in buffer[start + 2:end]:
            if not is_hex(c):
                return False
        return True

    if valid_hex_number(buffer, start, end) or buffer[start:end].isdigit():
        return lex_Number
    c = buffer[start]
    if is_rtl_ident_char(c):
        return lex_Identifier
    switcher = {
        '(': lex_OpenParen,
        ')': lex_CloseParen,
        '[': lex_OpenBracket,
        ']': lex_CloseBracket,
        '{': lex_code_string,
        '"': lex_c_string,
        '-': lex_negative_number,
    }
    handler = switcher.get(c, None)
    if handler == None:
        raise ValueError()
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

class Iterator:
    def __init__(self, ast):
        def strip(v):
            if v[0] == ASTKind.List or v[0] == ASTKind.Vector:
                print("warning: input error", v, file=sys.stderr)
                assert(len(v[1]) == 1)
                return v[1][0][1]
            return v[1]
        l = ast[1]
        self.name = l[1][1]
        members = []
        for m in l[2][1]:
            if m[0] == ASTKind.List or m[0] == ASTKind.Vector:
                members.append((m[1][0][1], strip(m[1][1])))
            else:
                members.append((m[1], ""))
        self.members = members

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{{name: {}, members: {}}}'.format(self.name, self.members)

class IteratorAttribute:
    def __init__(self, ast):
        l = ast[1]
        self.name = l[1][1]
        members = []
        for m in l[2][1]:
            if m[0] == ASTKind.List or m[0] == ASTKind.Vector:
                # (V8BF ("TARGET_BF16_SIMD")
                members.append((m[1][0][1], m[1][1][1]))
            else:
                members.append((m[1], ""))
        self.members = members

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '{{name: {}, members: {}}}'.format(self.name, self.members)

class Elaborator():
    def __init__(self, working_dir):
        super().__init__()
        self.working_dir = working_dir
        if self.working_dir[-1] != '/':
            self.working_dir += '/'
        self.elab_init()
        self.all_mode_itors = {}
        self.all_mode_attrs = {}
        self.all_int_itors = {}
        self.all_int_attrs = {}
        self.all_code_itors = {}
        self.all_code_attrs = {}

    def dump_all_itors(self, os=sys.stderr):
        print('all_mode_itors: {}'.format(self.all_mode_itors), file=os)
        print('all_mode_attrs: {}'.format(self.all_mode_attrs), file=os)
        print('all_code_itors: {}'.format(self.all_code_itors), file=os)
        print('all_code_attrs: {}'.format(self.all_code_attrs), file=os)
        print('all_int_itors: {}'.format(self.all_int_itors), file=os)
        print('all_int_attrs: {}'.format(self.all_int_attrs), file=os)

    def bad(self, ast, message):
        return (ASTKind.Bad, (message, ast))

    @staticmethod
    def split_identifier(id:str):
        ids = []
        id_len = len(id)
        start = 0
        end = 0
        nested = 0
        for end in range(id_len):
            c = id[end]
            if c == '<':
                nested += 1
            elif c == '>':
                nested -= 1
            elif c == ':':
                if nested == 0:
                    ids.append(id[start:end])
                    start = end + 1
        if start != id_len:
            ids.append(id[start:id_len])
        l = len(ids)
        if l > 2:
            print(l, id, ids, file=sys.stderr)
            raise ValueError()
        elif l == 2:
            return (ids[0], ids[1])
        else:
            return (id, None)

    @staticmethod
    def split_identifier_for_substitute(name:str):
        ids = []
        id_len = len(name)
        start = 0
        end = 0
        nested = 0
        for end in range(id_len):
            c = name[end]
            if c == '<':
                nested += 1
                if nested == 1 and start != end:
                    ids.append(name[start:end])
                    start = end
            elif c == '>':
                nested -= 1
                if nested == 0:
                    ids.append(name[start:end + 1])
                    start = end + 1
            elif c == ':':
                if nested == 0:
                    if start != end:
                        ids.append(name[start:end])
                    ids.append(':')
                    start = end + 1
        if start != id_len:
            ids.append(name[start:id_len])
        return ids

    def try_find_mode_itor(self, mode):
        itor = self.all_mode_itors.get(mode, None)
        if itor == None:
            return
        self.mode_itor[itor] = 0

    def try_find_int_itor(self, i):
        itor = self.all_int_itors.get(i, None)
        if itor == None:
            return
        self.int_itor[itor] = 0
            
    def try_find_code_itor(self, code):
        itor = self.all_code_itors.get(code, None)
        if itor == None:
            return
        self.code_itor[itor] = 0

    def find_itors(self, ast):
        k = ast[0]
        if k == ASTKind.Number:
            return
        if k == ASTKind.Identifier or k == ASTKind.String:
            idn, mode = Elaborator.split_identifier(ast[1])
            if mode != None:
                self.try_find_mode_itor(mode)
            else:
                self.try_find_int_itor(idn)
            self.try_find_code_itor(idn)

        if k == ASTKind.List or k == ASTKind.Vector:
            for m in ast[1]:
                self.find_itors(m)

    def elab_init(self):
        self.mode_itor = {}
        self.int_itor = {}
        self.code_itor = {}

    def do_substitute(self, ast):
        switcher = {
            ASTKind.Identifier: self.substitute_identifier,
            ASTKind.Number: self.substitute_number,
            ASTKind.String: self.substitute_string,
            ASTKind.List: self.substitute_list,
            ASTKind.Vector: self.substitute_vector,
        }
        handler = switcher[ast[0]]
        return handler(ast)

    @staticmethod
    def get_list_form(ast):
        if ast[0] == ASTKind.List:
            if len(ast[1]) > 0:
                return ast[1][0][1]
        return None

    def elab(self, ast_):
        asts = [ast_]
        form = Elaborator.get_list_form(ast_)
        if form != None:
            switcher = {
                'include': self.handle_include,
                "define_mode_iterator": self.handle_define_mode_iterator,
                "define_mode_attr": self.handle_define_mode_attr,
                "define_code_iterator": self.handle_define_code_iterator,
                "define_code_attr": self.handle_define_code_attr,
                "define_int_iterator": self.handle_define_int_iterator,
                "define_int_attr": self.handle_define_int_attr,
            }
            handler = switcher.get(form, None)
            if handler != None:
                ast_ = handler(ast_)
                if isinstance(ast_, list):
                    asts = ast_
                else:
                    asts = [ast_]
        def bump(d):
            for k in d:
                if d[k] + 1 < len(k.members):
                    d[k] += 1
                    return True
                else:
                    d[k] = 0
            return False
        result = []
        for ast in asts:
            self.elab_init()
            self.find_itors(ast)
            while True:
                result.append(self.do_substitute(ast))
                if bump(self.mode_itor) or bump(self.int_itor) or bump(self.code_itor):
                    continue
                else:
                    break;
        return result

    def try_substitute_mode(self, s):
        print('to_substitute: ', s)
        if len(s) < 2 or s[0] != '<' or s[-1] != '>':
            return s
        s1 = s[1:-1]
        print('to_substitute s1: ', s1)
        print(self.mode_itor)
        for k in self.mode_itor:
            print(k.name, s1)
            if k.name == s1:
                print('substitute: ', k.members[self.mode_itor[k]][0])
                return k.members[self.mode_itor[k]][0]
        return s

    def try_substitute_code(self, s):
        if len(s) < 2 or s[1] != '<' or s[-1] != '>':
            return s
        s1 = s[1:-1]
        for k in self.code_itor:
            if k.name == s1:
                return k.members[self.code_itor[k]][0]
        return s

    def substitute_string_impl(self, name):
        ids = Elaborator.split_identifier_for_substitute(name)
        has_mode = len(ids) >= 2 and ids[-2] == ':'
        if has_mode:
            ids[-1] = self.try_substitute_mode(ids[-1])
        for i in range(len(ids)):
            ids[i] = self.try_substitute_mode(self.try_substitute_code(ids[i]))
        return ids

    def substitute_identifier(self, ast):
        assert(ast[0] == ASTKind.Identifier)
        return (ASTKind.Identifier, "".join(self.substitute_string_impl(ast[1])))

    def substitute_number(self, ast):
        return ast

    def substitute_string(self, ast):
        assert(ast[0] == ASTKind.String)
        return (ASTKind.String, "".join(self.substitute_string_impl(ast[1])))

    def substitute_vector(self, ast):
        assert(ast[0] == ASTKind.Vector)
        return (ASTKind.Vector, [self.do_substitute(x) for x in ast[1]])

    def substitute_list(self, ast):
        assert(ast[0] == ASTKind.List)
        return (ASTKind.List, [self.do_substitute(x) for x in ast[1]])

    def include_handler_impl(self, path):
        result = []
        lexer = Lexer(self.working_dir + path)
        syntax_trees = parse_rtl_file(lexer)
        for tree in syntax_trees:
            t = self.elab(tree)
            if isinstance(t, list):
                result += t
            else:
                result.append(t)
        return result

    def handle_include(self, ast):
        include_spec = ast[1][1]
        if include_spec[0] == ASTKind.String:
            return self.include_handler_impl(include_spec[1])
        elif include_spec[0] == ASTKind.List:
            result = []
            for spec in include_spec[1]:
                result += self.include_handler_impl(spec[1])
            return result
        return []

    def handle_define_mode_iterator(self, ast):
        itor = Iterator(ast)
        self.all_mode_itors[itor.name] = itor
        return ast

    def handle_define_mode_attr(self, ast):
        attr = IteratorAttribute(ast)
        self.all_mode_attrs[attr.name] = attr
        return ast

    def handle_define_code_iterator(self, ast):
        itor = Iterator(ast)
        self.all_code_itors[itor.name] = itor
        return ast

    def handle_define_code_attr(self, ast):
        attr = IteratorAttribute(ast)
        self.all_code_attrs[attr.name] = attr
        return ast

    def handle_define_int_iterator(self, ast):
        itor = Iterator(ast)
        self.all_int_itors[itor.name] = itor
        return ast

    def handle_define_int_attr(self, ast):
        attr = IteratorAttribute(ast)
        self.all_int_attrs[attr.name] = attr
        return ast

    def elab_list(self, ast):
        lst = ast[1]
        if len(lst) == 0:
            return [self.bad(ast, "")]
        if lst[0][0] != ASTKind.Identifier:
            return [self.bad(ast, "")]
        idn = lst[0][1]
        switcher = {
        }
        handler = switcher.get(idn, None)
        if handler != None:
            return [handler(ast)]
        return [ast]

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

def parse_rtl_file(lexer: Lexer):
    result = []
    while lexer.next < len(lexer.buffer):
        result.append(parse_rtl_list(lexer))
    return result

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
    if isinstance(ast, ASTKind):
        print(ast, file=sys.stderr)
    switcher[ast[0]](ast, indent, os)

if __name__ == '__main__':
    lexer = Lexer(sys.argv[1])
    syntax_trees = parse_rtl_file(lexer)
    elaborator = Elaborator(sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(sys.argv[1]))
    result = []
    for tree in syntax_trees:
        t = elaborator.elab(tree)
        if isinstance(t, list):
            result += t
        else:
            result.append(t)
    #for t in result:
    #    dump_ast(t)
    switcher = {
        'define_insn': lambda x: print(x[1][1][1])
    }
    for t in result:
        h = Elaborator.get_list_form(t)
        handler = switcher.get(h, None)
        if handler != None:
            handler(t)
    elaborator.dump_all_itors(os=sys.stdout)
