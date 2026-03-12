import random
from .ui import C

ARTS = [
    # Spiderman
    rf"""{C.RED}
           _.-"___"-._
         .'--.`   `.--'.
        /.'   \   /   `.\ 
       |/.-.-.-\-/-.-.-.\|
       |/.-.-.-\-/-.-.-.\|
        \ \   /   \   / /
         \ `.'     `.' /
          `._       _.'
             `""\"""`
    {C.RESET}""",
    
    # Darth Vader
    rf"""{C.GRAY}
               _.-'~~~~'-._
             /   _      _   \ 
            |  /'o\    /o'\  |
            |  |___|  |___|  |
            |       \/       |
             \      ||      /
              |    /||\    |
              |___/||||\___|
    {C.RESET}""",

    # Batman
    rf"""{C.YELLOW}
           _==/          i     i          \==_
         /XX/            |\___/|            \XX\ 
       /XXXX\            |XXXXX|            /XXXX\ 
      |XXXXXX\_         _XXXXXXX_         _/XXXXXX|
     XXXXXXXXXXXxxxxxxxXXXXXXXXXXXxxxxxxxXXXXXXXXXXX
    |XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX|
    XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    |XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX|
     XXXXXX/^^^^"\XXXXXXXXXXXXXXXXXXXXX/^^^^^\XXXXXX
      |XXX|       \XXX/^^\XXXXX/^^\XXX/       |XXX|
        \X\         \X\    \X/    /X/         /X/
           \         \X\         /X/         /
    {C.RESET}""",

    # Lightsaber / Jedi
    rf"""{C.BLUE}
      .  .
    . \ | / .
   . -- * -- .
    . / | \ .
      .  .
        |
        |
       [#]
       [|]
       [|]
      /   \ 
    {C.RESET}""",

    # Baby Yoda / Grogu
    rf"""{C.GREEN}
          ___          _____          ___
         /   \        /     \        /   \ 
        /     \      | () () |      /     \ 
       /       \____.\  ^  /.____/       \ 
      /_____.---'     `---'     `---._____\ 
    {C.RESET}""",

    # Homer Simpson
    rf"""{C.YELLOW}
          ___  ___
        /     \  /  \ 
       |       ||    |
       |       ||    |
        \_____/  \__/
        /     \      \ 
       |       |      |
       |  (o)  | (o)  |
        \     /      /
         `---'___---'
    {C.RESET}""",
    
    # Iron Man
    rf"""{C.RED}
           ___
         /`   `\ 
        |  \|/  |
        |   |   |
         \  |  /
           | |
           | |
          /___\ 
    {C.RESET}""",
    
    # Deadpool
    rf"""{C.RED}
         ,-'""`-.
       ,'        `.
      /    _  _    \ 
      |   (o)(o)   |
      \    `--'    /
       `.        .'
         `-....-'
    {C.RESET}""",
    
    # The Matrix
    rf"""{C.GREEN}
      0 1 0 0 1 1 0
      1  {C.WHITE}Wake up, {C.GREEN} 1
      0  {C.WHITE}Neo...   {C.GREEN} 0
      1 0 1 1 0 1 1
    {C.RESET}"""
]

def get_random_art():
    return random.choice(ARTS)
