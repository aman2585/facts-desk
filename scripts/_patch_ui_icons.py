from pathlib import Path

p = Path(__file__).resolve().parents[1] / "ui" / "assets" / "app.js"
t = p.read_text(encoding="utf-8")
pairs = [
    (
        '<span class="material-symbols-outlined text-on-primary text-[14px]">smart_toy</span>',
        "${icon('bot', 'text-[14px] text-on-primary')}",
    ),
    (
        '<span class="material-symbols-outlined text-[18px]">thumb_up</span>',
        "${icon('thumbUp', 'text-[18px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[18px]">thumb_down</span>',
        "${icon('thumbDown', 'text-[18px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[18px]">content_copy</span>',
        "${icon('copy', 'text-[18px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[16px] text-primary">description</span>',
        "${icon('doc', 'text-[16px] text-primary')}",
    ),
    (
        '<span class="material-symbols-outlined text-[14px] opacity-50 ml-0.5">open_in_new</span>',
        "${icon('external', 'text-[14px] opacity-50 ml-0.5')}",
    ),
    (
        '<span class="material-symbols-outlined text-[16px]">info</span>',
        "${icon('info', 'text-[16px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[14px] opacity-50">open_in_new</span>',
        "${icon('external', 'text-[14px] opacity-50')}",
    ),
    (
        '<span class="material-symbols-outlined text-outline mt-0.5 shrink-0">search_off</span>',
        "${icon('searchOff', 'text-outline mt-0.5 shrink-0 text-[20px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[16px]">description</span>',
        "${icon('doc', 'text-[16px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[18px]">open_in_new</span>',
        "${icon('external', 'text-[18px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-on-surface-variant opacity-60 group-hover:opacity-100 transition-opacity">arrow_forward</span>',
        "${icon('arrow', 'text-on-surface-variant opacity-60 group-hover:opacity-100 transition-opacity')}",
    ),
    (
        '<span class="material-symbols-outlined text-[14px] text-on-error-container">warning</span>',
        "${icon('warning', 'text-[14px] text-on-error-container')}",
    ),
    (
        '<span class="material-symbols-outlined text-error mt-0.5">cloud_off</span>',
        "${icon('cloudOff', 'text-error mt-0.5 text-[20px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-[18px]">refresh</span>',
        "${icon('refresh', 'text-[18px]')}",
    ),
    (
        '<span class="material-symbols-outlined text-on-surface-variant group-active:text-primary transition-colors">arrow_forward</span>',
        "${icon('arrow', 'text-on-surface-variant group-active:text-primary transition-colors')}",
    ),
]
for a, b in pairs:
    if a not in t:
        print("MISSING:", a[:70])
    else:
        t = t.replace(a, b)
        print("ok:", a[:50])
p.write_text(t, encoding="utf-8")
print("remaining material-symbols:", t.count("material-symbols"))
