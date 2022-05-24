cmake_minimum_required(VERSION 3.13)
project(calc)

set(CMAKE_CXX_STANDARD 11)

add_custom_command(
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.flex
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.cpp
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/calc_parser.hpp
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/calc_typedef.hpp
    OUTPUT ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.hpp
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/calc.py
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/playlang/cplusplus.py
    DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/test_py.py
    COMMAND python3 ${CMAKE_CURRENT_SOURCE_DIR}/calc.py 
        --namespace calc 
        --include calc.hpp
        --typedef ${CMAKE_CURRENT_BINARY_DIR}/calc_typedef.hpp 
        --parser ${CMAKE_CURRENT_BINARY_DIR}/calc_parser.hpp
        --flex ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.flex
    COMMAND flex 
        --yyclass=calc::Tokenizer 
        --header-file=${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.hpp
        -o ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.cpp 
        ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.flex
)

include_directories(${CMAKE_CURRENT_BINARY_DIR})
include_directories(${CMAKE_CURRENT_SOURCE_DIR})
add_executable(clac 
    calc.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.cpp
    ${CMAKE_CURRENT_BINARY_DIR}/calc_tokenizer.hpp
    ${CMAKE_CURRENT_BINARY_DIR}/calc_parser.hpp
    ${CMAKE_CURRENT_BINARY_DIR}/calc_typedef.hpp
)
