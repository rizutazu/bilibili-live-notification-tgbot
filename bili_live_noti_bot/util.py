def isValidPositiveInt(input: str) -> bool:
    """
        判断是否为格式正确的正整数
    """
    return input.isnumeric() and input.isascii() and int(input) > 0 and str(int(input)) == input