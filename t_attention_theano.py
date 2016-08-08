import numpy as np
import theano as theano
import theano.tensor as T
from theano.gradient import grad_clip
import time
import operator

class GRUTheano:

    def __init__(self, word_dim, hidden_dim=100, bptt_truncate=-1):
        # Assign instance variables
        self.word_dim = word_dim
        self.hidden_dim = hidden_dim
        self.bptt_truncate = bptt_truncate
        # Initialize the network parameters
        E = np.random.uniform(-np.sqrt(1./word_dim), np.sqrt(1./word_dim), (hidden_dim-3, word_dim))
        Ey_encode = np.zeros(3)
        Ey_decode = np.identity(3)
        U = np.random.uniform(-np.sqrt(1./hidden_dim), np.sqrt(1./hidden_dim), (12, hidden_dim, hidden_dim))
        W = np.random.uniform(-np.sqrt(1./hidden_dim), np.sqrt(1./hidden_dim), (12, hidden_dim, hidden_dim))
        V = np.random.uniform(-np.sqrt(1./hidden_dim), np.sqrt(1./hidden_dim), (3, hidden_dim))
        b = np.zeros((12, hidden_dim))
        c = np.zeros(3)
        # Theano: Created shared variables
        self.E = theano.shared(name='E', value=E.astype(theano.config.floatX))
        self.Ey_encode = theano.shared(name='Ey_encode', value=Ey_encode.astype(theano.config.floatX))
        self.Ey_decode = theano.shared(name='Ey_decode', value=Ey_decode.astype(theano.config.floatX))
        self.U = theano.shared(name='U', value=U.astype(theano.config.floatX))
        self.W = theano.shared(name='W', value=W.astype(theano.config.floatX))
        self.V = theano.shared(name='V', value=V.astype(theano.config.floatX))
        self.b = theano.shared(name='b', value=b.astype(theano.config.floatX))
        self.c = theano.shared(name='c', value=c.astype(theano.config.floatX))
        # SGD / rmsprop: Initialize parameters
        self.mE = theano.shared(name='mE', value=np.zeros(E.shape).astype(theano.config.floatX))
        self.mEy_encode = theano.shared(name='mEy_encode', value=np.zeros(Ey_encode.shape).astype(theano.config.floatX))
        self.mEy_decode = theano.shared(name='mEy_decode', value=np.zeros(Ey_decode.shape).astype(theano.config.floatX))
        self.mU = theano.shared(name='mU', value=np.zeros(U.shape).astype(theano.config.floatX))
        self.mV = theano.shared(name='mV', value=np.zeros(V.shape).astype(theano.config.floatX))
        self.mW = theano.shared(name='mW', value=np.zeros(W.shape).astype(theano.config.floatX))
        self.mb = theano.shared(name='mb', value=np.zeros(b.shape).astype(theano.config.floatX))
        self.mc = theano.shared(name='mc', value=np.zeros(c.shape).astype(theano.config.floatX))
        # We store the Theano graph here
        self.theano = {}
        self.__theano_build__()

    def __theano_build__(self):
        E, Ey_encode, Ey_decode, V, U, W, b, c = self.E, self.Ey_encode, self.Ey_decode, self.V, self.U, self.W, self.b, self.c

        x = T.ivector('x')
        y = T.ivector('y')

        def forward_prop_step_encode_backward(x_t, s_t1_prev_b, s_t2_prev_b, s_t3_prev_b, c_t1_prev_b, c_t2_prev_b, c_t3_prev_b):
            # This is how we calculated the hidden state in a simple RNN. No longer!
            # s_t = T.tanh(U[:,x_t] + W.dot(s_t1_prev))

            # Word embedding layer
            x_e_b = E[:,x_t]
            xy_e_b = theano.tensor.concatenate([x_e_b,Ey_encode], axis=0)

            #Encode   #LSTM Layer 1
            # i=z, f=r, add o,
            i_t1_b = T.nnet.hard_sigmoid(U[0].dot(xy_e_b) + W[0].dot(s_t1_prev_b) + b[0])
            f_t1_b = T.nnet.hard_sigmoid(U[1].dot(xy_e_b) + W[1].dot(s_t1_prev_b) + b[1])
            o_t1_b = T.nnet.hard_sigmoid(U[2].dot(xy_e_b) + W[2].dot(s_t1_prev_b) + b[2])
            g_t1_b = T.tanh(U[3].dot(xy_e_b) + W[3].dot(s_t1_prev_b) + b[3])
            c_t1_b = c_t1_prev_b*f_t1_b + g_t1_b*i_t1_b
            s_t1_b = T.tanh(c_t1_b)*o_t1_b

            # LSTM Layer 2
            i_t2_b = T.nnet.hard_sigmoid(U[4].dot(s_t1_b) + W[4].dot(s_t2_prev_b) + b[4])
            f_t2_b = T.nnet.hard_sigmoid(U[5].dot(s_t1_b) + W[5].dot(s_t2_prev_b) + b[5])
            o_t2_b = T.nnet.hard_sigmoid(U[6].dot(s_t1_b) + W[6].dot(s_t2_prev_b) + b[6])
            g_t2_b = T.tanh(U[7].dot(s_t1_b) + W[7].dot(s_t2_prev_b) + b[7])
            c_t2_b = c_t2_prev_b * f_t2_b + g_t2_b * i_t2_b
            s_t2_b = T.tanh(c_t2_b) * o_t2_b

            # LSTM Layer 3
            i_t3_b = T.nnet.hard_sigmoid(U[8].dot(s_t2_b) + W[8].dot(s_t3_prev_b) + b[8])
            f_t3_b = T.nnet.hard_sigmoid(U[9].dot(s_t2_b) + W[9].dot(s_t3_prev_b) + b[9])
            o_t3_b = T.nnet.hard_sigmoid(U[10].dot(s_t2_b) + W[10].dot(s_t3_prev_b) + b[10])
            g_t3_b = T.tanh(U[11].dot(s_t2_b) + W[11].dot(s_t3_prev_b) + b[11])
            c_t3_b = c_t3_prev_b * f_t3_b + g_t3_b * i_t3_b
            s_t3_b = T.tanh(c_t3_b) * o_t3_b

            return [s_t1_b, s_t2_b, s_t3_b, c_t1_b, c_t2_b, c_t3_b]

        def forward_prop_step_encode(x_t, s_t1_prev, s_t2_prev, s_t3_prev, c_t1_prev, c_t2_prev, c_t3_prev):
            # This is how we calculated the hidden state in a simple RNN. No longer!
            # s_t = T.tanh(U[:,x_t] + W.dot(s_t1_prev))

            # Word embedding layer
            x_e = E[:,x_t]
            xy_e = theano.tensor.concatenate([x_e,Ey_encode], axis=0)

            #Encode   #LSTM Layer 1
            # i=z, f=r, add o,
            i_t1 = T.nnet.hard_sigmoid(U[0].dot(xy_e) + W[0].dot(s_t1_prev) + b[0])
            f_t1 = T.nnet.hard_sigmoid(U[1].dot(xy_e) + W[1].dot(s_t1_prev) + b[1])
            o_t1 = T.nnet.hard_sigmoid(U[2].dot(xy_e) + W[2].dot(s_t1_prev) + b[2])
            g_t1 = T.tanh(U[3].dot(xy_e) + W[3].dot(s_t1_prev) + b[3])
            c_t1 = c_t1_prev*f_t1 + g_t1*i_t1
            s_t1 = T.tanh(c_t1)*o_t1

            # LSTM Layer 2
            i_t2 = T.nnet.hard_sigmoid(U[4].dot(s_t1) + W[4].dot(s_t2_prev) + b[4])
            f_t2 = T.nnet.hard_sigmoid(U[5].dot(s_t1) + W[5].dot(s_t2_prev) + b[5])
            o_t2 = T.nnet.hard_sigmoid(U[6].dot(s_t1) + W[6].dot(s_t2_prev) + b[6])
            g_t2 = T.tanh(U[7].dot(s_t1) + W[7].dot(s_t2_prev) + b[7])
            c_t2 = c_t2_prev * f_t2 + g_t2 * i_t2
            s_t2 = T.tanh(c_t2) * o_t2

            # LSTM Layer 3
            i_t3 = T.nnet.hard_sigmoid(U[8].dot(s_t2) + W[8].dot(s_t3_prev) + b[8])
            f_t3 = T.nnet.hard_sigmoid(U[9].dot(s_t2) + W[9].dot(s_t3_prev) + b[9])
            o_t3 = T.nnet.hard_sigmoid(U[10].dot(s_t2) + W[10].dot(s_t3_prev) + b[10])
            g_t3 = T.tanh(U[11].dot(s_t2) + W[11].dot(s_t3_prev) + b[11])
            c_t3 = c_t3_prev * f_t3 + g_t3 * i_t3
            s_t3 = T.tanh(c_t3) * o_t3

            # Final output calculation
            # Theano's softmax returns a matrix with one row, we only need the row
            #o_t = T.nnet.softmax(V.dot(s_t3) + c)[0]

            return [s_t1, s_t2, s_t3, c_t1, c_t2, c_t3]

        def forward_prop_step_decode(x_t, y_t, s_t1_matrix, s_t2_matrix, s_t3_matrix, s_t1_prev_d, s_t2_prev_d, s_t3_prev_d, c_t1_prev_d, c_t2_prev_d, c_t3_prev_d):
            # This is how we calculated the hidden state in a simple RNN. No longer!
            # s_t = T.tanh(U[:,x_t] + W.dot(s_t1_prev))

            # Word embedding layer
            x_e = E[:, x_t]
            y_e = Ey_decode[:,y_t]
            xy_e_d = theano.tensor.concatenate([x_e, y_e], axis=0)

            #Add s_xt to s_t_pre
            s_t1_prev_d = s_t1_prev_d * s_t1_matrix[x_t]
            s_t2_prev_d = s_t2_prev_d * s_t2_matrix[x_t]
            s_t3_prev_d = s_t3_prev_d * s_t3_matrix[x_t]

            # Decode   #LSTM Layer 1
            i_t1_d = T.nnet.hard_sigmoid(U[0].dot(xy_e_d) + W[0].dot(s_t1_prev_d) + b[0])
            f_t1_d = T.nnet.hard_sigmoid(U[1].dot(xy_e_d) + W[1].dot(s_t1_prev_d) + b[1])
            o_t1_d = T.nnet.hard_sigmoid(U[2].dot(xy_e_d) + W[2].dot(s_t1_prev_d) + b[2])
            g_t1_d = T.tanh(U[3].dot(xy_e_d) + W[3].dot(s_t1_prev_d) + b[3])
            c_t1_d = c_t1_prev_d * f_t1_d + g_t1_d * i_t1_d
            s_t1_d = T.tanh(c_t1_d) * o_t1_d

            # LSTM Layer 2
            i_t2_d = T.nnet.hard_sigmoid(U[4].dot(s_t1_d) + W[4].dot(s_t2_prev_d) + b[4])
            f_t2_d = T.nnet.hard_sigmoid(U[5].dot(s_t1_d) + W[5].dot(s_t2_prev_d) + b[5])
            o_t2_d = T.nnet.hard_sigmoid(U[6].dot(s_t1_d) + W[6].dot(s_t2_prev_d) + b[6])
            g_t2_d = T.tanh(U[7].dot(s_t1_d) + W[7].dot(s_t2_prev_d) + b[7])
            c_t2_d = c_t2_prev_d * f_t2_d + g_t2_d * i_t2_d
            s_t2_d = T.tanh(c_t2_d) * o_t2_d

            # LSTM Layer 3
            i_t3_d = T.nnet.hard_sigmoid(U[8].dot(s_t2_d) + W[8].dot(s_t3_prev_d) + b[8])
            f_t3_d = T.nnet.hard_sigmoid(U[9].dot(s_t2_d) + W[9].dot(s_t3_prev_d) + b[9])
            o_t3_d = T.nnet.hard_sigmoid(U[10].dot(s_t2_d) + W[10].dot(s_t3_prev_d) + b[10])
            g_t3_d = T.tanh(U[11].dot(s_t2_d) + W[11].dot(s_t3_prev_d) + b[11])
            c_t3_d = c_t3_prev_d * f_t3_d + g_t3_d * i_t3_d
            s_t3_d = T.tanh(c_t3_d) * o_t3_d

            # Final output calculation
            # Theano's softmax returns a matrix with one row, we only need the row
            o = T.nnet.softmax(V.dot(s_t3_d) + c)[0]

            return [o, s_t1_d, s_t2_d, s_t3_d, c_t1_d, c_t2_d, c_t3_d]

        def forward_prop_step_decode_test(x_t, o_t_pre_test, s_t1_matrix, s_t2_matrix, s_t3_matrix, s_t1_prev_d_test, s_t2_prev_d_test, s_t3_prev_d_test, c_t1_prev_d_test, c_t2_prev_d_test, c_t3_prev_d_test):
            # This is how we calculated the hidden state in a simple RNN. No longer!
            # s_t = T.tanh(U[:,x_t] + W.dot(s_t1_prev))

            # Word embedding layer
            x_e = E[:, x_t]
            #y_e = Ey[:, y_t]
            xy_e_d_test = theano.tensor.concatenate([x_e, o_t_pre_test], axis=0)

            #Add s_xt to s_t_pre
            s_t1_prev_d_test = s_t1_prev_d_test * s_t1_matrix[x_t]
            s_t2_prev_d_test = s_t2_prev_d_test * s_t2_matrix[x_t]
            s_t3_prev_d_test = s_t3_prev_d_test * s_t3_matrix[x_t]

            # Decode   #LSTM Layer 1
            i_t1_d_test = T.nnet.hard_sigmoid(U[0].dot(xy_e_d_test) + W[0].dot(s_t1_prev_d_test) + b[0])
            f_t1_d_test = T.nnet.hard_sigmoid(U[1].dot(xy_e_d_test) + W[1].dot(s_t1_prev_d_test) + b[1])
            o_t1_d_test = T.nnet.hard_sigmoid(U[2].dot(xy_e_d_test) + W[2].dot(s_t1_prev_d_test) + b[2])
            g_t1_d_test = T.tanh(U[3].dot(xy_e_d_test) + W[3].dot(s_t1_prev_d_test) + b[3])
            c_t1_d_test = c_t1_prev_d_test * f_t1_d_test + g_t1_d_test * i_t1_d_test
            s_t1_d_test = T.tanh(c_t1_d_test) * o_t1_d_test

            # LSTM Layer 2
            i_t2_d_test = T.nnet.hard_sigmoid(U[4].dot(s_t1_d_test) + W[4].dot(s_t2_prev_d_test) + b[4])
            f_t2_d_test = T.nnet.hard_sigmoid(U[5].dot(s_t1_d_test) + W[5].dot(s_t2_prev_d_test) + b[5])
            o_t2_d_test = T.nnet.hard_sigmoid(U[6].dot(s_t1_d_test) + W[6].dot(s_t2_prev_d_test) + b[6])
            g_t2_d_test = T.tanh(U[7].dot(s_t1_d_test) + W[7].dot(s_t2_prev_d_test) + b[7])
            c_t2_d_test = c_t2_prev_d_test * f_t2_d_test + g_t2_d_test * i_t2_d_test
            s_t2_d_test = T.tanh(c_t2_d_test) * o_t2_d_test

            # LSTM Layer 3
            i_t3_d_test = T.nnet.hard_sigmoid(U[8].dot(s_t2_d_test) + W[8].dot(s_t3_prev_d_test) + b[8])
            f_t3_d_test = T.nnet.hard_sigmoid(U[9].dot(s_t2_d_test) + W[9].dot(s_t3_prev_d_test) + b[9])
            o_t3_d_test = T.nnet.hard_sigmoid(U[10].dot(s_t2_d_test) + W[10].dot(s_t3_prev_d_test) + b[10])
            g_t3_d_test = T.tanh(U[11].dot(s_t2_d_test) + W[11].dot(s_t3_prev_d_test) + b[11])
            c_t3_d_test = c_t3_prev_d_test * f_t3_d_test + g_t3_d_test * i_t3_d_test
            s_t3_d_test = T.tanh(c_t3_d_test) * o_t3_d_test

            # Final output calculation
            # Theano's softmax returns a matrix with one row, we only need the row
            o_test = T.nnet.softmax(V.dot(s_t3_d_test) + c)[0]

            return [o_test, s_t1_d_test, s_t2_d_test, s_t3_d_test, c_t1_d_test, c_t2_d_test, c_t3_d_test]

        [s_t1_b, s_t2_b, s_t3_b, c_t1_b, c_t2_b, c_t3_b], updates = theano.scan(
            forward_prop_step_encode_backward,
            sequences=x[::-1], #reverse y
            truncate_gradient=self.bptt_truncate,
            outputs_info=[dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim))])

        [s_t1, s_t2, s_t3, c_t1, c_t2, c_t3], updates = theano.scan(
            forward_prop_step_encode,
            sequences=x,
            truncate_gradient=self.bptt_truncate,
            outputs_info=[dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim)),
                          dict(initial=T.zeros(self.hidden_dim))])
        [o, s_t1_d, s_t2_d, s_t3_d, c_t1_d, c_t2_d, c_t3_d], updates = theano.scan(
            forward_prop_step_decode,
            sequences=[x,T.concatenate([[y[-1]],y[:-1]], axis=0)],
            nonsequences = [s_t1, s_t2, s_t3],
            truncate_gradient=self.bptt_truncate,
            outputs_info=[None,
                          dict(initial=s_t1[-1]+s_t1_b[-1]),
                          dict(initial=s_t2[-1]+s_t2_b[-1]),
                          dict(initial=s_t3[-1]+s_t3_b[-1]),
                          dict(initial=c_t1[-1]+c_t1_b[-1]),
                          dict(initial=c_t2[-1]+c_t2_b[-1]),
                          dict(initial=c_t3[-1]+c_t3_b[-1])])

        [o_test, s_t1_d_test, s_t2_d_test, s_t3_d_test, c_t1_d_test, c_t2_d_test, c_t3_d_test], updates = theano.scan(
            forward_prop_step_decode_test,
            sequences=x,
            nonsequences=[s_t1, s_t2, s_t3],
            truncate_gradient=self.bptt_truncate,
            outputs_info=[dict(initial=T.zeros(3)),
                          dict(initial=s_t1[-1]+s_t1_b[-1]),
                          dict(initial=s_t2[-1]+s_t2_b[-1]),
                          dict(initial=s_t3[-1]+s_t3_b[-1]),
                          dict(initial=c_t1[-1]+c_t1_b[-1]),
                          dict(initial=c_t2[-1]+c_t2_b[-1]),
                          dict(initial=c_t3[-1]+c_t3_b[-1])])

        prediction = T.argmax(o_test, axis=1)
        o_error = T.sum(T.nnet.categorical_crossentropy(o, y))

        # Total cost (could add regularization here)
        cost = o_error

        # Gradients
        dE = T.grad(cost, E)
        dU = T.grad(cost, U)
        dW = T.grad(cost, W)
        db = T.grad(cost, b)
        dV = T.grad(cost, V)
        dc = T.grad(cost, c)

        # Assign functions
        self.predict = theano.function([x], o_test)
        self.predict_class = theano.function([x], prediction)
        self.ce_error = theano.function([x, y], cost)
        self.bptt = theano.function([x, y], [dE, dU, dW, db, dV, dc])

        # SGD parameters
        learning_rate = T.scalar('learning_rate')
        decay = T.scalar('decay')

        # rmsprop cache updates
        mE = decay * self.mE + (1 - decay) * dE ** 2
        mU = decay * self.mU + (1 - decay) * dU ** 2
        mW = decay * self.mW + (1 - decay) * dW ** 2
        mV = decay * self.mV + (1 - decay) * dV ** 2
        mb = decay * self.mb + (1 - decay) * db ** 2
        mc = decay * self.mc + (1 - decay) * dc ** 2

        self.sgd_step = theano.function(
            [x, y, learning_rate, theano.Param(decay, default=0.9)],
            [],
            updates=[(E, E - learning_rate * dE / T.sqrt(mE + 1e-6)),
                     (U, U - learning_rate * dU / T.sqrt(mU + 1e-6)),
                     (W, W - learning_rate * dW / T.sqrt(mW + 1e-6)),
                     (V, V - learning_rate * dV / T.sqrt(mV + 1e-6)),
                     (b, b - learning_rate * db / T.sqrt(mb + 1e-6)),
                     (c, c - learning_rate * dc / T.sqrt(mc + 1e-6)),
                     (self.mE, mE),
                     (self.mU, mU),
                     (self.mW, mW),
                     (self.mV, mV),
                     (self.mb, mb),
                     (self.mc, mc)
                    ])


    def calculate_total_loss(self, X, Y):
        return np.sum([self.ce_error(x,y) for x,y in zip(X,Y)])

    def calculate_loss(self, X, Y):
        # Divide calculate_loss by the number of words
        num_words = np.sum([len(y) for y in Y])
        return self.calculate_total_loss(X,Y)/float(num_words)
