import matplotlib as mpl
mpl.use('agg')
import numpy as np
from pycuda import compiler, gpuarray, tools
import pycuda.driver as cuda
import time
import matplotlib.pyplot as plt

# Initialize the device
import pycuda.autoinit
plt.ioff()

class DWT_optimized:
    def __init__(self):
        # Grid size should be (ceil((N + maskwidth - 1)/2), M) for input image shape (M, N) to avoid wasting threads
        # and to make indexing work
        
        self.dwt_forward1_opt= """
        __global__ void w_kernel_forward1(float* input, float* tmp_a1, float* tmp_a2, float* filter_lo, float* filter_hi){
            // params:
            // float* input: input image of shape (M, N)
            // float* tmp_a1: subband 1 subject to second forward pass
            // float* tmp_a2: subband 2 subject to second forward pass
            // float* filter_lo: LPF coefficients for approximation of shape (hlen,)
            // float* filter_hi: HPF coefficients for detail of shape (hlen,)
              
            int Row = threadIdx.y + blockIdx.y*blockDim.y;
            int Col = threadIdx.x + blockIdx.x*blockDim.x;
            
            // Obtain the dimension of the problem
            // size of the mask, width and height of input image
            // int maskwidth: length of the filter (default is 10 for CDF9/7)
            // int H: number of rows for input (height) (equals to M)
            // int W: number of columns for input (width) (equals to N)
            int maskwidth = %(M)s;
            int H = %(H)s;
            int W = %(W)s;

            // Obtain half of the width
            // int flag_W_odd = (W & 1);
            // int W_half = (W + flag_W_odd)/2;
            int W_half = (W + maskwidth - 1)/2;
            
            // Perform vertical downsampling by half (separable method for DWT)
            // Output is of shape (M, ceil((N + maskwidth - 1)/2))
            if (Row < H && Col < W_half){
                // c: center of filter
                // hL: number of filter elements to the left of center
                // hR: number of filter elements to the right of center
                int c;
                
                if (maskwidth & 1) { 
                // odd kernel size
                    c = maskwidth/2;
                    // int hL = c;
                    // int hR = c;
                }
                else { 
                // even kernel size : center is shifted to the left
                    c = maskwidth/2 + 3;
                    // int hL = c + 2;
                    // int hR = c - 1;
                }
                
                // 1D Convolution with zeropadding boundary constraints
                // Convolution is performed along each row
                float res_tmp_a1 = 0, res_tmp_a2 = 0;
                
                // Note the downsampling via multiplication with 2
                int N_start_col = Col * 2 - c;
                
                for (int j = 0; j < maskwidth; j++) {
                    int curCol = N_start_col + j;
                    int kerIdx = maskwidth - j - 1;
                    
                    // Apply the zero-padding via the conditional
                    if ((curCol > -1) && (curCol < W)){
                        // Perform the convolution with both filters
                        res_tmp_a1 += input[Row * W + curCol] * filter_lo[kerIdx];
                        res_tmp_a2 += input[Row * W + curCol] * filter_hi[kerIdx];
                    }
                }
                
                tmp_a1[Row * W_half + Col] = res_tmp_a1;
                tmp_a2[Row * W_half + Col] = res_tmp_a2;
            }
        }
        """

#         self.dwt_forward1_opt = """
#         __global__ void w_kernel_forward1(float* input, float* tmp_a1, float* tmp_a2, float* filter_lo, float* filter_hi){
#             // params:
#             // float* input: input image of shape (M, N)
#             // float* tmp_a1: subband 1 subject to second forward pass
#             // float* tmp_a2: subband 2 subject to second forward pass
#             // float* filter_lo: LPF coefficients for approximation of shape (hlen,)
#             // float* filter_hi: HPF coefficients for detail of shape (hlen,)
             
#             //define shared memory input
#             __shared__ float ds_input[32][32]; 
            
#             //row-major format rows and columns
#             int Row = threadIdx.y + blockIdx.y*blockDim.y;
#             int Col = threadIdx.x + blockIdx.x*blockDim.x;
            
#             // Obtain the dimension of the problem
#             // size of the mask, width and height of input image
#             // int maskwidth: length of the filter (default is 10 for CDF9/7)
#             // int H: number of rows for input (height) (equals to M)
#             // int W: number of columns for input (width) (equals to N)
#             int maskwidth = %(M)s;
#             int H = %(H)s;
#             int W = %(W)s;

#             // Obtain half of the width
#             // int flag_W_odd = (W & 1);
#             // int W_half = (W + flag_W_odd)/2;
#             int W_half = (W + maskwidth - 1)/2;
            
#              // Get center of filer, hL, hR
#              if (Row < H && Col < W_half){
#                 // c: center of filter
#                 // hL: number of filter elements to the left of center
#                 // hR: number of filter elements to the right of center
#                 int c;

#                 if (maskwidth & 1) { 
#                 // odd kernel size
#                     c = maskwidth/2;
#                 }
#                 else { 
#                 // even kernel size : center is shifted to the left
#                     c = maskwidth/2 + 3;
#                 }
#             }
            
#             //For each tile
#             for(int t=0; t < ((W-1)/TILE_WIDTH + 1); ++t){
            
#                 //load image into shared memory
#                 if(Col < H && t*TILE_WIDTH + ty < W){
#                     ds_input[ty][tx] = input[(t*TILE_WIDTH + ty)* H + Col];
#                 }
#                 else{
#                     ds_B[ty][tx] = 0.0;
#                 }
#                 __syncthreads();
                   
#             }
            
#             //output data if in range, fill tmp_a1, tmp_a2
#             if(Row < H && Col < W_half){
#                 tmp_a1[Row * W_half + Col] = res_tmp_a1;
#                 tmp_a2[Row * W_half + Col] = res_tmp_a2;
#             }
                
                
            
#             // Perform vertical downsampling by half (separable method for DWT)
#             // Output is of shape (M, ceil((N + maskwidth - 1)/2))
#             if (Row < H && Col < W_half){
#                 // c: center of filter
#                 // hL: number of filter elements to the left of center
#                 // hR: number of filter elements to the right of center
#                 int c;
                
#                 if (maskwidth & 1) { 
#                 // odd kernel size
#                     c = maskwidth/2;
#                 }
#                 else { 
#                 // even kernel size : center is shifted to the left
#                     c = maskwidth/2 + 3;
#                 }
                
#                 // 1D Convolution with zeropadding boundary constraints
#                 // Convolution is performed along each row
#                 float res_tmp_a1 = 0, res_tmp_a2 = 0;
                
#                 // Note the downsampling via multiplication with 2
#                 int N_start_col = Col * 2 - c;
                
#                 for (int j = 0; j < maskwidth; j++) {
#                     int curCol = N_start_col + j;
#                     int kerIdx = maskwidth - j - 1;
                    
#                     // Apply the zero-padding via the conditional
#                     if ((curCol > -1) && (curCol < W)){
#                         // Perform the convolution with both filters
#                         res_tmp_a1 += input[Row * W + curCol] * filter_lo[kerIdx];
#                         res_tmp_a2 += input[Row * W + curCol] * filter_hi[kerIdx];
#                     }
#                 }
                
#                 tmp_a1[Row * W_half + Col] = res_tmp_a1;
#                 tmp_a2[Row * W_half + Col] = res_tmp_a2;
#             }
#         }
#         """
        # Grid size should be (ceil((N + maskwidth - 1)/2), ceil((M + maskwidth - 1)/2)) for input image shape (M, N)
        # to avoid wasting threads
        self.dwt_forward2_opt = """
        __global__ void w_kernel_forward2(float* tmp_a1, float* tmp_a2, float* c_a, float* c_h, float* c_v, float* c_d, float* filter_lo, float* filter_hi, int W, int H, int maskwidth){
        
            // params:
            // float* tmp_a1: subband 1 subject to second forward pass
            // float* tmp_a2: subband 2 subject to second forward pass
            // float* c_a: approximation coefficients, shape (ceil((M + maskwidth - 1)/2), ceil((N + maskwidth - 1)/2))
            // float* c_h: horizontal detail coefficients, shape (ceil((M + maskwidth - 1)/2), ceil((N + maskwidth - 1)/2))
            // float* c_v: vertical detail coefficients, shape (ceil((M + maskwidth - 1)/2), ceil((N + maskwidth - 1)/2))
            // float* c_d: diagonal detail coefficients, shape (ceil((M + maskwidth - 1)/2), ceil((N + maskwidth - 1)/2))

            // float* filter_lo: LPF coefficients for approximation of shape (hlen,)
            // float* filter_hi: HPF coefficients for detail of shape (hlen,)
            
            // int H: height of subband arrays
            // int W: width of subband arrays
            
            //allocate shared memory for subbands (shape (block_width = 16, blockwidth+maskwidth-1 = 25))
            //note the allocated memory is non-square since our convolution is only being applied horizontally
            __shared__ float ds_tmp_a1[16][25]; 
            __shared__ float ds_tmp_a2[16][25];

            //row-major row column format
            int Row = threadIdx.y + blockIdx.y*blockDim.y;
            int Col = threadIdx.x + blockIdx.x*blockDim.x;

            // Obtain the dimension of the problem
            // size of the mask, width and height of input image
            // int maskwidth: length of the filter (default is 10 for CDF9/7)
            // int H: number of rows for input (height) (equals to M)
            // int W: number of columns for input (width) (equals to N)

            // Obtain half of the width
            int H_half = (H + maskwidth - 1)/2;
            int W_half = (W + maskwidth - 1)/2;
            
            //load tmp a1 and a2 into shared memory
            int radius = maskwidth/2;
            int dest = threadIdx.y * 25 + threadIdx.x; //1D index for destination idx of shared mem
            int destY = dest / 25;
            int destX = dest % 16; //Get the destination x/y indicies
            int srcY = blockIdx.y * 16 + destY - radius;
            int srcX = blockIdx.x * 25 + destX - radius; //TODO: check this logic for scrY/scrX; confident dest idxs are correct
            int src = srcY * W + srcX;
            
            //only load the subbands into shared memory if boundary conditions are satisfied
            if (srcY >= 0 && srcY < H && srcX >= 0 && srcX < W)
            {
                    ds_tmp_a1[destY][destX] = tmp_a1[src];
                    ds_tmp_a2[destY][destX] = tmp_a2[src];
            }
            else
            {
                    ds_tmp_a1[destY][destX] = 0;
                    ds_tmp_a2[destY][destX] = 0;
            }

            //perorm second batch loading of subband arrays; again only if boundary conditions are satisfied
            dest = threadIdx.y * 25 + threadIdx.x + 25 * 16; //1D index for destination idx of shared mem
            destY = dest / 25;
            destX = dest % 16; //Get the destination x/y indicies
            srcY = blockIdx.y * 25 + destY - radius;
            srcX = blockIdx.x * 16 + destX - radius; //same TODO as before
            src = srcY * W + srcX;
            if (destY < W) {
                if (srcY >= 0 && srcY < H && srcX >= 0 && srcX < W) {
                    ds_tmp_a1[destY][destX] = tmp_a1[src];
                    ds_tmp_a2[destY][destX] = tmp_a2[src];
                } else {
                    ds_tmp_a1[destY][destX] = 0;
                    ds_tmp_a2[destY][destX] = 0;
                }
            }
            
            //synchronize all threads such that tiles are loaded correctly
            __syncthreads();
            
            //zero padding boundary conditions for 1D convoluton
            float res_a = 0, res_h = 0, res_v = 0, res_d = 0;
            
            
            // c: center of filter
            // hL: number of filter elements to the left of center
            // hR: number of filter elements to the right of center
            int c;
            // Perform horizontal downsampling by half (separable method for DWT)
            // Output is of shape (ceil((M + maskwidth - 1)/2), ceil((N + maskwidth - 1)/2))
            if (Row < H_half && Col < W_half){
                
                if (maskwidth & 1) { 
                // odd kernel size
                    c = maskwidth/2;
                    // hL = c;
                    // hR = c;
                }
                else { 
                // even kernel size : center is shifted to the left
                    c = maskwidth/2 + 3;
                    // hL = c;
                    // hR = c + 1;
                }
            }
            
            if (Row < H_half && Col < W_half){
                //Perform 1D convolution with zero padding, but store output arrays into shared memory
                for (int x = 0; x < maskwidth; x++) {
                    int curRow = Row * 2 - c + x;
                    int kerIdx = maskwidth - x - 1;
                    // Apply the zero-padding via the conditional
                    if ((curRow > -1) && (curRow < H)){
                        // Perform the convolution with both filters
                     
                        //Index the normal y dimension block size but for x, take into account
                        //the convolution operation (max x dim = 16+9 = 25 -> max index 24)
                        res_a += ds_tmp_a1[threadIdx.y][threadIdx.x+x] * filter_lo[kerIdx];
                        res_h += ds_tmp_a1[threadIdx.y][threadIdx.x+x] * filter_hi[kerIdx];
                        res_v += ds_tmp_a2[threadIdx.y][threadIdx.x+x] * filter_lo[kerIdx];
                        res_d += ds_tmp_a2[threadIdx.y][threadIdx.x+x] * filter_hi[kerIdx];
                    }
                }
           }

            //output filter coeffecients as result of convolution
            if (Row < H && Col < W){
                c_a[Row * W_half + Col] = res_a;
                c_h[Row * W_half + Col] = res_h;
                c_v[Row * W_half + Col] = res_v;
                c_d[Row * W_half + Col] = res_d;
            }
            
            //call synchreads, control divergence maximum complexity of O(4*maskwidth + ~20)
            __syncthreads();
            
        }
        """

    def dwt_gpu_optimized(self, h_input, filters):
        
        # Obtain the shape of the input matrix
        dim_M = h_input.shape[0]
        dim_N = h_input.shape[1]
        maskwidth = filters[0].shape[0]

        # Obtain the filters
        filters = filters.astype(np.float32)
        h_filter_lo = filters[0, :]
        h_fitler_hi = filters[1, :]

        # Compute the size of the output of the wavelet transform
        dim_R = int(np.ceil(((dim_M + maskwidth - 1)/2)))
        dim_C = int(np.ceil(((dim_N + maskwidth - 1)/2)))

        # Set the width of the block
        BLOCK_WIDTH = 16
        BLOCK_WIDTH_X_OPT = 25

        # Calculate the number of blocks
        # Note that final output has shape (M, N)
        # Note block width x for optomized version same as shared memory size
        BLOCK_X = int(np.ceil(dim_C / float(BLOCK_WIDTH)))
        BLOCK_X_OPT = int(np.ceil(dim_C / float(BLOCK_WIDTH_X_OPT)))
        BLOCK_Y1 = int(np.ceil(dim_M / float(BLOCK_WIDTH)))
        BLOCK_Y2 = int(np.ceil(dim_R / float(BLOCK_WIDTH)))

        h_input = h_input.astype(np.float32)
        h_tmp_a1 = np.zeros(shape=(dim_M, dim_C), dtype=np.float32)
        h_tmp_a2 = np.zeros(shape=(dim_M, dim_C), dtype=np.float32)

        h_cA = np.zeros(shape=(dim_R, dim_C), dtype=np.float32)
        h_cH = np.zeros(shape=(dim_R, dim_C), dtype=np.float32)
        h_cV = np.zeros(shape=(dim_R, dim_C), dtype=np.float32)
        h_cD = np.zeros(shape=(dim_R, dim_C), dtype=np.float32)

        # Transfer data to device
        d_input = gpuarray.to_gpu(h_input)
        d_tmp_a1 = gpuarray.to_gpu(h_tmp_a1)
        d_tmp_a2 = gpuarray.to_gpu(h_tmp_a2)

        d_cA = gpuarray.to_gpu(h_cA)
        d_cH = gpuarray.to_gpu(h_cH)
        d_cV = gpuarray.to_gpu(h_cV)
        d_cD = gpuarray.to_gpu(h_cD)

        d_filter_lo = gpuarray.to_gpu(h_filter_lo)
        d_filter_hi = gpuarray.to_gpu(h_fitler_hi)

        # Call kernel
        dwt_forward1_optimized_kernel = self.dwt_forward1_opt % {
            'M': maskwidth,
            'H': dim_M,
            'W': dim_N
        }

        dwt_forward2_optimized_kernel = self.dwt_forward2_opt

        # Call kernel function
        prg_dwt_forward1_optimized = compiler.SourceModule(dwt_forward1_optimized_kernel)
        prg_dwt_forward2_optimized = compiler.SourceModule(dwt_forward2_optimized_kernel)
        dwt_forward1_optimized = prg_dwt_forward1_optimized.get_function("w_kernel_forward1")
        dwt_forward2_optimized = prg_dwt_forward2_optimized.get_function("w_kernel_forward2")
        tic = cuda.Event()
        toc = cuda.Event()

        tic.record()
        dwt_forward1_optimized(d_input, d_tmp_a1, d_tmp_a2, d_filter_lo, d_filter_hi,
                           block=(BLOCK_WIDTH, BLOCK_WIDTH, 1), grid=(BLOCK_X, BLOCK_Y1, 1))
        dwt_forward2_optimized(d_tmp_a1, d_tmp_a2, d_cA, d_cH, d_cV, d_cD, d_filter_lo, d_filter_hi, np.int32(dim_N), np.int32(dim_M), np.int32(maskwidth),
                           block=(BLOCK_WIDTH_X_OPT, BLOCK_WIDTH, 1), grid=(BLOCK_X_OPT, BLOCK_Y2, 1))
        toc.record()
        toc.synchronize()

        kernel_time = tic.time_till(toc)*1e-3
        h_cA = d_cA.get()
        h_cH = d_cH.get()
        h_cV = d_cV.get()
        h_cD = d_cD.get()

        return h_cA, h_cH, h_cV, h_cD, kernel_time
