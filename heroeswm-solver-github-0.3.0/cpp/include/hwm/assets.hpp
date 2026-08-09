#pragma once
#include <filesystem>
#include <string>

namespace hwm {
inline std::string resolve_asset(const std::string& relative) {
    namespace fs = std::filesystem;
    std::error_code ec;
    fs::path p(relative);
    if (fs::exists(p, ec)) return p.string();
#ifdef HWM_PROJECT_ROOT
    fs::path rooted = fs::path(HWM_PROJECT_ROOT) / p;
    ec.clear();
    if (fs::exists(rooted, ec)) return rooted.string();
#endif
    return relative;
}
}
