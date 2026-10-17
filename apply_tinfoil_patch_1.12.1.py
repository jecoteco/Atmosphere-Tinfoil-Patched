#!/usr/bin/env python3
from pathlib import Path
import sys

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()

files = {
    "process": ROOT / "libraries/libmesosphere/source/kern_k_process.cpp",
    "scheduler": ROOT / "libraries/libmesosphere/source/kern_k_scheduler.cpp",
    "thread": ROOT / "libraries/libmesosphere/source/svc/kern_svc_thread.cpp",
    "arm": ROOT / "libraries/libvapours/include/vapours/svc/arch/arm/svc_thread_local_region.hpp",
    "arm64": ROOT / "libraries/libvapours/include/vapours/svc/arch/arm64/svc_thread_local_region.hpp",
}

for p in files.values():
    if not p.is_file():
        raise SystemExit(f"Missing expected Atmosphere source file: {p}")

def replace_exact(path, old, new, label):
    data = path.read_text(encoding="utf-8")
    count = data.count(old)
    if count != 1:
        raise SystemExit(
            f"{label}: expected exactly one match in {path}, found {count}. "
            "Refusing to patch an unexpected source revision."
        )
    path.write_text(data.replace(old, new, 1), encoding="utf-8", newline="\n")
    print(f"Patched: {path.relative_to(ROOT)}")

for key in ("process", "thread"):
    p = files[key]
    data = p.read_text(encoding="utf-8")
    occurrences = data.count("->thread_handle")
    if occurrences != 1:
        raise SystemExit(
            f"{p}: expected exactly one ->thread_handle occurrence, found {occurrences}."
        )
    p.write_text(data.replace("->thread_handle", "->current_thread_handle", 1),
                 encoding="utf-8", newline="\n")
    print(f"Patched: {p.relative_to(ROOT)}")

old_scheduler = '''        /* Set the new Thread Local region. */
        const auto tls_address = GetInteger(next_thread->GetThreadLocalRegionAddress());
        cpu::SwitchThreadLocalRegion(tls_address);

        /* Update the thread's cpu time differential in TLS, if relevant. */
        if (tls_address != 0) {
            static_cast<ams::svc::ThreadLocalRegion *>(next_thread->GetThreadLocalRegionHeapAddress())->thread_cpu_time = next_thread->GetCpuTime() - cur_tick;
        }'''
new_scheduler = '''        /* Set the new Thread Local region. */
        cpu::SwitchThreadLocalRegion(GetInteger(next_thread->GetThreadLocalRegionAddress()));'''
replace_exact(files["scheduler"], old_scheduler, new_scheduler, "scheduler TLS compatibility")

old_arm64 = '''    struct ThreadLocalRegion {
        u32 message_buffer[MessageBufferSize / sizeof(u32)];
        volatile u16 disable_count;
        volatile u16 interrupt_flag;
        volatile u8 cache_maintenance_flag;
        volatile s64 thread_cpu_time;
        volatile ams::svc::Handle thread_handle;
        /* TODO: How should we handle libnx vs Nintendo user thread local space? */
        uintptr_t TODO[(0x200 - 0x114) / sizeof(uintptr_t)];
    };
    static_assert(__builtin_offsetof(ThreadLocalRegion, disable_count)          == 0x100);
    static_assert(__builtin_offsetof(ThreadLocalRegion, interrupt_flag)         == 0x102);
    static_assert(__builtin_offsetof(ThreadLocalRegion, cache_maintenance_flag) == 0x104);
    static_assert(__builtin_offsetof(ThreadLocalRegion, thread_cpu_time)        == 0x108);'''

new_arm64 = '''    struct ThreadLocalRegion {
        u32 message_buffer[MessageBufferSize / sizeof(u32)];
        volatile u16 disable_count;
        volatile u16 interrupt_flag;
        volatile u8  cache_maintenance_flag;
        u8           reserved[3];
        u64          thread_cpu_time;
        u32          current_thread_handle;
        u8           reserved2[0x6C];
        u8           tls[0x50];
        uintptr_t    locale_ptr;
        uintptr_t    errno_val;
        uintptr_t    thread_data;
        uintptr_t    eh_globals;
        uintptr_t    thread_pointer;
        uintptr_t    thread_type;
    };
    static_assert(__builtin_offsetof(ThreadLocalRegion, disable_count)          == 0x100);
    static_assert(__builtin_offsetof(ThreadLocalRegion, interrupt_flag)         == 0x102);
    static_assert(__builtin_offsetof(ThreadLocalRegion, cache_maintenance_flag) == 0x104);
    static_assert(__builtin_offsetof(ThreadLocalRegion, current_thread_handle)  == 0x110);'''
replace_exact(files["arm64"], old_arm64, new_arm64, "AArch64 TLR layout")

old_arm = '''    struct ThreadLocalRegion {
        u32 message_buffer[MessageBufferSize / sizeof(u32)];
        volatile u16 disable_count;
        volatile u16 interrupt_flag;
        volatile u8 cache_maintenance_flag;
        volatile s64 thread_cpu_time;
        volatile ams::svc::Handle thread_handle;
        /* TODO: Should we bother adding the Nintendo aarch32 thread local context here? */
        uintptr_t TODO[(0x200 - 0x114) / sizeof(uintptr_t)];
    };'''

new_arm = '''    struct ThreadLocalRegion {
        u32 message_buffer[MessageBufferSize / sizeof(u32)];
        volatile u16 disable_count;
        volatile u16 interrupt_flag;
        /* TODO: Should we bother adding the Nintendo aarch32 thread local context here? */
        uintptr_t TODO[(0x200 - 0x104) / sizeof(uintptr_t)];
    };'''
replace_exact(files["arm"], old_arm, new_arm, "AArch32 TLR layout")

print()
print("Atmosphere 1.12.1 Tinfoil compatibility source patch applied successfully.")
