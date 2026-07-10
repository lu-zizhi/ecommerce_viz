import os

def generate_tree(path, prefix='', ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = {'venv', '__pycache__', '.git', '.idea'}

    try:
        items = os.listdir(path)
    except PermissionError:
        return

    dirs = sorted([i for i in items if os.path.isdir(os.path.join(path, i))
                   and i not in ignore_dirs])
    files = sorted([i for i in items if os.path.isfile(os.path.join(path, i))])
    all_items = dirs + files

    skip_files = {'generate_tree.py', 'check_data.py',
                  'check_models.py', 'reset_db.py'}

    filtered = [i for i in all_items if i not in skip_files]

    for i, item in enumerate(filtered):
        is_last = (i == len(filtered) - 1)
        connector = '└── ' if is_last else '├── '
        item_path = os.path.join(path, item)

        if os.path.isdir(item_path):
            print(f'{prefix}{connector}{item}/')
            extension = '    ' if is_last else '│   '
            generate_tree(item_path, prefix + extension, ignore_dirs)
        else:
            print(f'{prefix}{connector}{item}')

print('ecommerce_viz/')
generate_tree('.')