#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void vulnerable_function(char* input) {
    char buffer[16];
    strcpy(buffer, input); // Buffer overflow vulnerability
    printf("Input: %s\n", buffer);
}

int add_numbers(int a, int b) {
    return a + b;
}

int multiply_numbers(int a, int b) {
    return a * b;
}

int calculate(int a, int b, char op) {
    int result;
    
    switch(op) {
        case '+':
            result = add_numbers(a, b);
            break;
        case '*':
            result = multiply_numbers(a, b);
            break;
        default:
            printf("Unsupported operation\n");
            result = 0;
    }
    
    return result;
}

int main(int argc, char** argv) {
    printf("Starting test program...\n");
    
    int x = 5;
    int y = 7;
    int z = calculate(x, y, '+');
    
    printf("%d + %d = %d\n", x, y, z);
    
    z = calculate(x, y, '*');
    printf("%d * %d = %d\n", x, y, z);
    
    if (argc > 1) {
        vulnerable_function(argv[1]);
    } else {
        printf("No input provided\n");
    }
    
    printf("Program completed\n");
    return 0;
} 