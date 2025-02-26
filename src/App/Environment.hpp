#pragma once

#include "Core/Facades/Runtime.hpp"

namespace App::Env
{
inline std::filesystem::path TweaksDir()
{
    return Core::Runtime::GetRootDir() / L"r6" / L"tweaks";
}
}
