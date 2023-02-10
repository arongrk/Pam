import tomllib

with open("config.toml", "rb") as f:
    config = tomllib.load(f)

print(config['matlabdata'])
print("abc><def")